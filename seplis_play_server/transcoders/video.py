import os, asyncio, sys
import shutil
from fastapi import Query
from typing import Dict, Literal, Optional, Annotated
from pydantic import BaseModel, constr, validator
from seplis_play_server import config, logger, constants

class Transcode_settings(BaseModel):

    play_id: constr(min_length=1)
    session: constr(min_length=1)
    supported_video_codecs: Annotated[list[constr(min_length=1)], Query()]
    supported_audio_codecs: Annotated[list[constr(min_length=1)], Query()]
    supported_pixel_formats: Annotated[list[constr(min_length=1)], Query()]
    format: Literal['pipe', 'hls', 'dash']
    transcode_video_codec: Literal['h264', 'hevc', 'vp9']
    transcode_audio_codec: Literal['aac', 'opus', 'dts', 'flac', 'mp3']
    transcode_pixel_format: Literal['yuv420p', 'yuv420p10le']

    start_time: Optional[int] | constr(max_length=0)
    audio_lang: Optional[str]
    audio_channels: Optional[int] | constr(max_length=0)
    width: Optional[int] | constr(max_length=0)
    video_bitrate: Optional[int] | constr(max_length=0)
    client_width: Optional[int] | constr(max_length=0)

    @validator('supported_video_codecs', 'supported_audio_codecs', 'supported_pixel_formats', pre=True, whole=True)
    def _b_as_json(cls, v):
        l = []
        for a in v:
            l.extend([s.strip() for s in a.split(',')])
        return l

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
    'aac': 'libfdk_aac',
    'dts': 'dca',
    'flac': 'flac',
    'mp3': 'libmp3lame',
}

class Stream_index(BaseModel):
    index: int
    group_index: int

class Transcoder:

    def __init__(self, settings: Transcode_settings, metadata: Dict):
        self.settings = settings
        self.metadata = metadata
        self.video_stream = self.get_video_stream()
        self.input_codec = self.video_stream['codec_name']
        self.output_codec_lib = None
        self.ffmpeg_args = None
        self.temp_folder = None
        

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
            ready = await asyncio.wait_for(self.wait_for_media(), timeout=60 if not config.debug else 20)
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
        self.ffmpeg_args = [            
            {'-analyzeduration': '200M'},
        ]
        self.set_hardware_decoder()
        self.ffmpeg_args.extend([
            {'-ss': str(self.settings.start_time or 0)},
            {'-autorotate': '0'},
            {'-i': self.metadata['format']['filename']},
            {'-y': None},
            {'-copyts': None},
            {'-start_at_zero': None},
            {'-avoid_negative_ts': 'disabled'},
            {'-muxdelay': '0'},
        ])
        self.set_video()
        self.set_audio()
        self.ffmpeg_extend_args()

    def set_hardware_decoder(self):
        if not config.ffmpeg_hwaccel_enabled:
            return

        if config.ffmpeg_hwaccel == 'qsv':
            self.ffmpeg_args.extend([
                {'-init_hw_device': f'vaapi=va:'},
                {'-init_hw_device': 'qsv=qs@va'},
                {'-filter_hw_device': 'qs'},
                {'-hwaccel': 'vaapi'},
                {'-hwaccel_output_format': 'vaapi'},
            ])

        elif config.ffmpeg_hwaccel == 'vaapi':
            self.ffmpeg_args.extend([
                {'-init_hw_device': f'vaapi=va:{config.ffmpeg_hwaccel_device}'},
                {'-hwaccel': 'vaapi'},
                {'-hwaccel_output_format': 'vaapi'},
            ])

    def set_video(self):
        codec = codecs_to_libary.get(self.settings.transcode_video_codec, self.settings.transcode_video_codec)

        self.ffmpeg_args.append({'-map_metadata': '-1'})
        self.ffmpeg_args.append({'-map_chapters': '-1'})
        self.ffmpeg_args.append({'-threads': '0'})

        if self.can_copy_video():
            codec = 'copy'
            self.ffmpeg_args.insert(0, {'-noaccurate_seek': None})
        else:
            if config.ffmpeg_hwaccel_enabled:
                codec = f'{self.settings.transcode_video_codec}_{config.ffmpeg_hwaccel}'
        self.output_codec_lib = codec
        self.ffmpeg_args.extend([
            {'-map': '0:v:0'},
            {'-c:v': codec},
        ])

        if codec == 'copy':
            return

        width = self.settings.width or self.settings.client_width or self.video_stream['width']
        if width > self.video_stream['width']:
            width = self.video_stream['width']

        if config.ffmpeg_hwaccel_enabled:
            self.ffmpeg_args.append({'-autoscale': '0'})
            if config.ffmpeg_hwaccel_low_powermode:
                self.ffmpeg_args.append({'-low_power': '1'})
        

        vf = self.get_filter(width)
        if vf:
            self.ffmpeg_args.append({'-vf': ','.join(vf)})
        self.ffmpeg_args.extend(self.get_quality_params(width, codec))


    def can_copy_video(self):
        if self.input_codec not in self.settings.supported_video_codecs:
            return False
        
        if self.video_stream['pix_fmt'] not in self.settings.supported_pixel_formats:
            return False

        if self.settings.width and self.settings.width < self.video_stream['width']:
            return False

        return True


    def get_filter(self, width: int):
        vf = []
        tonemap = False
        hdr = self.video_stream['pix_fmt'] == 'yuv420p10le' and \
                self.video_stream.get('color_primaries') == 'bt2020' and \
                self.video_stream.get('color_transfer') == 'smpte2084'

        if self.video_stream['pix_fmt'] in self.settings.supported_pixel_formats:
            pix_fmt = self.video_stream['pix_fmt']
        else:
            pix_fmt = self.settings.transcode_pixel_format
            tonemap = config.ffmpeg_tonemap_enabled and hdr  

        if (pix_fmt == 'yuv420p10le' or tonemap) and hdr:
            vf.append('setparams=color_primaries=bt2020:color_trc=smpte2084:colorspace=bt2020nc')
        else:            
            vf.append('setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709')

        if not config.ffmpeg_hwaccel_enabled:
            if width:
                vf.append(f'scale=width={width}:height=-2')
            vf.append(f'format={pix_fmt}')
            # missing software tonemap
            return
        
        if pix_fmt == 'yuv420p10le' and hdr:
            # fails with h264
            format_ = 'p010le' if self.settings.transcode_video_codec != 'h264' else 'nv12'
        else:            
            format_ = 'nv12'
            
        if tonemap:
            if config.ffmpeg_hwaccel in ('qsv', 'vaapi'): # SDR
                vf.append('tonemap_vaapi=format=nv12:p=bt709:t=bt709:m=bt709')
                # Brightness: b=0 - Contrast: c=1.2
                vf.append('procamp_vaapi=b=0:c=1.2:extra_hw_frames=16')            

        width_filter = f'w={width}:h=-2:' if width != self.video_stream['width'] else ''

        if config.ffmpeg_hwaccel == 'qsv':
            vf.append(f'scale_vaapi={width_filter}format={format_},hwmap=derive_device=qsv,format=qsv')

        else:
            vf.append(f'scale_{config.ffmpeg_hwaccel}={width_filter}format={format_}')

        return vf


    def get_quality_params(self, width: int, codec: str):
        params = []
        params.append({'-preset': config.ffmpeg_preset})
        if codec == 'libx264':
            params.append({'-x264opts': 'subme=0:me_range=4:rc_lookahead=10:me=hex:8x8dct=0:partitions=none'})
            if width >= 3840:
                params.append({'-crf': 18})
            elif width >= 1920:
                params.append({'-crf': 19})
            else:
                params.append({'-crf': 26})
                
        elif codec == 'libx265':
            params.extend([
                {'-tag:v': 'hvc1'},
                {'-x265-params': 'keyint=24:min-keyint=24'},
            ])
            if width >= 3840:
                params.append({'-crf': 18})
            elif width >= 3840:
                params.append({'-crf': 20})
            elif width >= 1920:
                params.append({'-crf': 22})
            else:
                params.append({'-crf': 31})

        elif codec == 'libvpx-vp9':
            params.append({'-g': '24'})
            if width >= 3840:
                params.append({'-crf': 15})
            elif width >= 2560:
                params.append({'-crf': 24})
            elif width >= 1920:
                params.append({'-crf': 31})
            else:
                params.append({'-crf': 34})

        elif codec  == 'h264_qsv':
            params.append({'-look_ahead': '0'})
            
        elif codec == 'hevc_qsv':
            params.append({'-tag:v': 'hvc1'})

        params.extend(self.get_video_bitrate_params(codec))
            
        return params


    def set_audio(self):
        index = self.stream_index_by_lang('audio', self.settings.audio_lang)
        stream = self.metadata['streams'][index.index]
        codec = codecs_to_libary.get(stream['codec_name'], '')
        
        if self.can_copy_audio(stream):
            codec = 'copy'
        else:
            if not codec or codec not in self.settings.supported_audio_codecs:
                codec = codecs_to_libary.get(self.settings.transcode_audio_codec, '')
            bitrate = stream.get('bit_rate', stream['channels'] * 128000)
            if self.settings.audio_channels and self.settings.audio_channels < stream['channels']:
                bitrate = self.settings.audio_channels * 128000
                self.ffmpeg_args.append({'-ac': self.settings.audio_channels})
            else:
                self.ffmpeg_args.append({'-ac': stream['channels']})
            self.ffmpeg_args.append({'-ab': bitrate})
        if not codec:
            raise Exception('No audio codec libary')
        self.ffmpeg_args.extend([
            {'-map': f'0:{index.index}'},
            {'-c:a': codec},
        ])

    def can_copy_audio(self, stream: dict):
        return False # Audio goes out of sync for some reason when using audio copy
        if self.settings.audio_channels and self.settings.audio_channels != stream['channels']:
            return False
            
        if stream['codec_name'] not in self.settings.supported_audio_codecs:
            return False

        return True


    def get_video_bitrate_params(self, codec: str):
        bitrate = self.get_video_bitrate()

        if codec in ('libx264', 'libx265', 'libvpx-vp9'):
            return [
                {'-maxrate': bitrate},
                {'-bufsize': bitrate*2},
            ]

        return [
            {'-b:v': bitrate},
            {'-maxrate': bitrate},
            {'-bufsize': bitrate*2},
        ]

    def get_video_bitrate(self):
        bitrate = self.settings.video_bitrate or int(self.metadata['format']['bit_rate'] or 0)

        if bitrate:
            upscaling = self.settings.width and self.settings.width > self.video_stream['width']
            # only allow bitrate increase if upscaling
            if not upscaling:
                bitrate = self._min_video_bitrate(int(self.metadata['format']['bit_rate']), bitrate)

            bitrate = self._video_scale_bitrate(bitrate, self.input_codec, self.settings.transcode_video_codec)
            
            # don't exceed the requested bitrate
            if self.settings.video_bitrate:
                bitrate = min(bitrate, self.settings.video_bitrate)

        # Make sure when calculating the bufsize (bitrate * 2) that it doesn't exceed the maxsize
        return min(bitrate or 0, sys.maxsize / 2)

    def _min_video_bitrate(self, input_bitrate: int, requested_bitrate: int):
        bitrate = input_bitrate
        if bitrate <= 2000000:
            bitrate = int(bitrate * 2.5)
        elif bitrate <= 3000000:
            bitrate *= 2
        return min(bitrate, requested_bitrate)

    def _video_bitrate_scale_factor(self, codec: str):
        if codec in ('hevc', 'vp9'):
            return .6
        if codec == 'av1':
            return .5
        return 1

    def _video_scale_bitrate(self, bitrate: int, input_codec: str, output_codec: str):
        input_scale_factor = self._video_bitrate_scale_factor(input_codec)
        output_scale_factor = self._video_bitrate_scale_factor(output_codec)
        scale_factor = output_scale_factor / input_scale_factor
        if bitrate <= 500000:
            scale_factor = max(scale_factor, 4)
        elif bitrate <= 1000000:
            scale_factor = max(scale_factor, 3)
        elif bitrate <= 2000000:
            scale_factor = max(scale_factor, 2.5)
        elif bitrate <= 3000000:
            scale_factor = max(scale_factor, 2)
        return int(scale_factor * bitrate)


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
        return 6 if self.output_codec_lib == 'copy' else 3


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
                l.append(str(value))
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