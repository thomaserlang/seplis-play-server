import os, asyncio
import shutil
from typing import Dict, Literal, Optional
from pydantic import BaseModel, constr
from seplis_play_server import config, logger

class Transcode_settings(BaseModel):

    play_id: constr(min_length=1)
    session: constr(min_length=1)
    supported_video_codecs: constr(min_length=1)
    supported_audio_codecs: constr(min_length=1)
    supported_pixel_formats: constr(min_length=1)
    format: Literal['pipe', 'hls', 'dash']
    transcode_video_codec: Literal['h264', 'hevc', 'vp9']
    transcode_audio_codec: constr(min_length=1)
    transcode_pixel_format: Literal['yuv420p', 'yuv420p10le']

    start_time: Optional[int] | constr(max_length=0)
    audio_lang: Optional[str]
    audio_channels: Optional[int] | constr(max_length=0)
    width: Optional[int] | constr(max_length=0)
    client_width: Optional[int] | constr(max_length=0)

class Session_model(BaseModel):
    process: asyncio.subprocess.Process
    temp_folder: Optional[str]
    call_later: asyncio.TimerHandle

    class Config:
        arbitrary_types_allowed = True

sessions: Dict[str, Session_model] = {}

codecs_to_libary = {
    'h264': 'libx264',
    'hevc': 'libx265',
    'vp9': 'libvpx-vp9',
    'opus': 'libopus',
}

class Stream_index(BaseModel):
    index: int
    group_index: int

class Transcoder:

    def __init__(self, settings: Transcode_settings, metadata: Dict):
        self.settings = settings
        self.metadata = metadata
        self.video_stream = self.get_video_stream()
        self.ffmpeg_args = None
        self.temp_folder = None
        self.codec = None

    async def start(self, send_data_callback=None) -> bool | bytes:
        self.temp_folder = self.create_temp_folder()
        if self.settings.session in sessions:
            try:
                return await asyncio.wait_for(self.wait_for_media(), timeout=5)
            except asyncio.TimeoutError:
                return False
        await self.set_ffmpeg_args()
        
        args = to_subprocess_arguments(self.ffmpeg_args)
        logger.debug(f'FFmpeg start args: {" ".join(args)}')
        self.process = await asyncio.create_subprocess_exec(
            os.path.join(config.ffmpeg_folder, 'ffmpeg'),
            *args,
            env=subprocess_env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.register_session()
        
        logger.debug(f'[{self.settings.session}] Waiting for media')
        ready = False
        try:
            ready = await asyncio.wait_for(self.wait_for_media(), timeout=60)
        except asyncio.TimeoutError:
            logger.error(f'[{self.settings.session}] Failed to create media, gave up waiting')
            try:
                self.process.terminate()
            except:
                pass
            return False

        return ready

    def ffmpeg_extend_args(self) -> None:
        pass

    def ffmpeg_change_args(self) -> None:
        pass

    async def wait_for_media(self) -> bool:
        pass
    
    def close(self) -> None:
        pass

    @property
    def media_path(self) -> str:
        pass

    @property
    def media_name(self) -> str:
        pass

    def register_session(self):
        loop = asyncio.get_event_loop()
        logger.info(f'[{self.settings.session}] Registered')
        sessions[self.settings.session] = Session_model(
            process=self.process,
            temp_folder=self.temp_folder,
            call_later=loop.call_later(
                config.session_timeout,
                close_session_callback,
                self.settings.session
            ),
        )

    async def set_ffmpeg_args(self):
        self.ffmpeg_args = []
        if config.ffmpeg_hwaccel_enabled:
            self.ffmpeg_args.append({'-hwaccel': config.ffmpeg_hwaccel})
            if config.ffmpeg_hwaccel_device:
                self.ffmpeg_args.append({'-hwaccel_device': config.ffmpeg_hwaccel_device})

        self.ffmpeg_args.extend([
            {'-analyzeduration': '200M'},
            {'-probesize': '200M'},
            {'-ss': str(self.settings.start_time or 0)},
            {'-i': self.metadata['format']['filename']},
            {'-y': None},
            {'-loglevel': 'quiet'},
            {'-preset:0': config.ffmpeg_preset},
            {'-copyts': None},
            {'-start_at_zero': None},
            {'-avoid_negative_ts': 'disabled'},
            {'-muxdelay': '0'},
        ])
        self.set_video()
        self.set_pix_format()
        self.set_audio()
        self.ffmpeg_extend_args()

    def set_video(self):
        codec = codecs_to_libary.get(self.settings.transcode_video_codec, self.settings.transcode_video_codec)
        self.codec = codec

        if self.video_stream['codec_name'] in self.settings.supported_video_codecs and \
            self.video_stream['pix_fmt'] in self.settings.supported_pixel_formats and \
            not self.settings.width:
            codec = 'copy'

        if codec != 'copy' and config.ffmpeg_hwaccel_enabled:
            self.ffmpeg_args.extend([
                {'-vf': f'scale_{config.ffmpeg_hwaccel}=format=nv12,hwupload'},
            ])
            codec = f'{self.settings.transcode_video_codec}_{config.ffmpeg_hwaccel}'

        self.ffmpeg_args.extend([
            {'-map': '0:v:0'},
            {'-c:v': codec},
        ])

        if codec == 'lib264':
            self.ffmpeg_args.extend([
                {'-x264opts': 'subme=0:me_range=4:rc_lookahead=10:me=hex:8x8dct=0:partitions=none'},
            ])
        elif codec == 'libx265':
            self.ffmpeg_args.extend([
                {'-tag:v': 'hvc1'},
                {'-x265-params': 'keyint=24:min-keyint=24'},
            ])
        elif codec == 'libvpx-vp9':
            self.ffmpeg_args.extend([
                {'-g': '24'},
            ])

        if codec == 'copy':
            self.ffmpeg_args.insert(0, {'-noaccurate_seek': None})
        else:
            width = self.settings.width or self.settings.client_width
            if not width or width > self.video_stream['width']:
                width = self.video_stream['width']
            if width < self.video_stream['width']:
                # keeps the aspect ratio for the height
                self.ffmpeg_args.append({'-filter:v': f'scale=width={width}:height=-2'})
            if not config.ffmpeg_hwaccel_enabled:
                self.ffmpeg_args.extend([
                    {'-crf': self._get_crf(width, codec)}
                ])

    def _get_crf(self, width, codec):
        crf = '23'
        if codec == 'libx264':
            crf = '26'
            if width >= 3840:
                crf = '18'
            elif width >= 1920:
                crf = '19'
        elif codec == 'libx265':
            crf = '31'
            if width >= 3840:
                crf = '18'
            elif width >= 3840:
                crf = '20'
            elif width >= 1920:
                crf = '22'
        elif codec == 'libvpx-vp9':
            crf = '34'
            if width >= 3840:
                crf = '15'
            elif width >= 2560:
                crf = '24'
            elif width >= 1920:
                crf = '31'
        return crf

    def set_pix_format(self):
        if self.video_stream['pix_fmt'] in self.settings.supported_pixel_formats:
            self.ffmpeg_args.append({'-pix_fmt': self.video_stream['pix_fmt']})
        else:
            self.ffmpeg_args.append({'-pix_fmt': self.settings.transcode_pixel_format})

    def set_audio(self):
        index = self.stream_index_by_lang('audio', self.settings.audio_lang)

        if self.settings.audio_channels:
            self.ffmpeg_args.append({'-ac': str(self.settings.audio_channels)})
        else:
            # Fix for hls eac3 or ac3 not playing or just no audio
            self.ffmpeg_args.append({'-ac': str(self.metadata['streams'][index.index]['channels'])})

        codec = codecs_to_libary.get(self.settings.transcode_audio_codec, self.settings.transcode_audio_codec)    
        self.ffmpeg_args.extend([
            {'-map': f'0:{index.index}'},
            {'-c:a': codec},
        ])

    def stream_index_by_lang(self, codec_type: str, lang: str):
        return stream_index_by_lang(self.metadata, codec_type, lang)

    def get_video_stream(self):
        return get_video_stream(self.metadata)

    def find_ffmpeg_arg(self, key):
        for a in self.ffmpeg_args:
            if key in a:
                return a[key]

    def change_ffmpeg_arg(self, key, new_value):
        for a in self.ffmpeg_args:
            if key in a:
                a[key] = new_value
                break

    def create_temp_folder(self):
        temp_folder = os.path.join(config.temp_folder, self.settings.session)
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)
        return temp_folder

    def segment_time(self):
        return 5 if self.find_ffmpeg_arg('-c:v') == 'copy' else 3

def subprocess_env():
    env = {}
    if config.ffmpeg_logfile:
        env['FFREPORT'] = f'file=\'{config.ffmpeg_logfile}\':level={config.ffmpeg_loglevel}'
    return env

def to_subprocess_arguments(args):
    l = []
    for a in args:
        for key, value in a.items():
            l.append(key)
            if value:
                l.append(value)
    return l

def subprocess_env() -> Dict:
    env = {}
    if config.ffmpeg_logfile:
        env['FFREPORT'] = f'file=\'{config.ffmpeg_logfile}\':level={config.ffmpeg_loglevel}'
    return env

def get_video_stream(metadata: Dict):
    for stream in metadata['streams']:
        if stream['codec_type'] == 'video':
            return stream
    if not stream:
        raise Exception('No video stream')

def stream_index_by_lang(metadata: Dict, codec_type:str, lang: str):
    logger.debug(f'Looking for {codec_type} with language {lang}')
    group_index = -1
    langs = []
    lang = '' if lang == None else lang
    index = None
    if ':' in lang:
        lang, index = lang.split(':')
        index = int(index)
        if index <= (len(metadata['streams']) - 1):
            stream = metadata['streams'][index]
            if 'tags' not in stream:
                index = None
            else:
                l = stream['tags'].get('language') or stream['tags'].get('title')
                if stream['codec_type'] != codec_type or l.lower() != lang.lower():
                    index = None
        else:
            index = None
    first = None
    for i, stream in enumerate(metadata['streams']):
        if stream['codec_type'] == codec_type:
            group_index += 1
            if not first:
                first = Stream_index(index=i, group_index=group_index)
            if lang == '':
                return first
            if 'tags' in stream:
                l = stream['tags'].get('language') or stream['tags'].get('title')
                if not l:
                    continue
                langs.append(l)
                if not index or stream['index'] == index:
                    if l.lower() == lang.lower():
                        return Stream_index(index=i, group_index=group_index)
    logger.warning(f'Found no {codec_type} with language: {lang}')
    logger.warning(f'Available {codec_type}: {", ".join(langs)}')
    return first

def close_session_callback(session):
    close_session(session)

def close_session(session):
    logger.info(f'[{session}] Closing')
    if session not in sessions:
        return
    s = sessions[session]
    try:
        s.process.kill()
    except:
        pass
    try:
        if s.temp_folder:
            if os.path.exists(s.temp_folder):
                shutil.rmtree(s.temp_folder)
            else:
                logger.warning(f'[{session}] Path: {s.temp_folder} not found, can\'t delete it')  
    except:
        pass          
    s.call_later.cancel()
    del sessions[session]
