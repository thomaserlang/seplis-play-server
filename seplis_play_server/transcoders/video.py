import asyncio
import os
import shutil
import sys
import uuid
from dataclasses import dataclass as pydataclass
from decimal import Decimal
from typing import Annotated, Dict, Literal, Optional

from fastapi import Query
from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
)
from pydantic.dataclasses import dataclass

from seplis_play_server import config, logger


@dataclass
class Transcode_settings:
    source_index: int
    play_id: Annotated[str, Query(min_length=1)]
    supported_video_codecs: Annotated[
        list[Annotated[str, Query(min_length=1)]], Query()
    ]
    supported_audio_codecs: Annotated[
        list[Annotated[str, Query(min_length=1)]], Query()
    ]
    format: Literal['pipe', 'hls', 'hls.js']
    transcode_video_codec: Literal['h264', 'hevc', 'vp9']
    transcode_audio_codec: Literal['aac', 'opus', 'dts', 'flac', 'mp3']

    session: Annotated[
        str, Query(default_factory=lambda: str(uuid.uuid4()), min_length=32)
    ]
    supported_video_containers: Annotated[
        list[Annotated[str, Query(min_length=1)]],
        Query(default_factory=lambda: ['mp4']),
    ]
    supported_hdr_formats: Annotated[
        list[Literal['hdr10', 'hlg', 'dovi', '']], Query(default_factory=lambda: [])
    ]
    supported_video_color_bit_depth: (
        Annotated[int, Query(ge=8)] | Annotated[str, Query(max_length=0)]
    ) = 10
    start_time: Annotated[Decimal, Query()] | Annotated[str, Query(max_length=0)] = (
        Decimal(0)
    )
    start_segment: int | Annotated[str, Query(max_length=0)] | None = None
    audio_lang: str | None = None
    max_audio_channels: int | None | Annotated[str, Query(max_length=0)] = None
    max_width: int | None | Annotated[str, Query(max_length=0)] = None
    max_video_bitrate: int | None | Annotated[str, Query(max_length=0)] = None
    client_can_switch_audio_track: bool = False
    # Currently there is an issue with Firefox and hls not being able to play if start time isn't 0 with video copy
    force_transcode: bool = False

    @field_validator(
        'supported_video_codecs',
        'supported_audio_codecs',
        'supported_hdr_formats',
        'supported_video_containers',
    )
    @classmethod
    def comma_string(cls, v):
        ll = []
        for a in v:
            ll.extend([s.strip() for s in a.split(',')])
        return ll

    def to_args_dict(self):
        from pydantic import RootModel

        settings_dict = RootModel[Transcode_settings](self).model_dump(
            exclude_none=True, exclude_unset=True
        )
        for key in settings_dict:
            if isinstance(settings_dict[key], list):
                settings_dict[key] = ','.join(settings_dict[key])
        return settings_dict


class Video_color(BaseModel):
    range: str
    range_type: str


@pydataclass
class Session_model:
    process: asyncio.subprocess.Process
    call_later: asyncio.TimerHandle
    transcode_folder: Optional[str] | None = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


sessions: Dict[str, Session_model] = {}

codecs_to_library = {
    'h264': 'libx264',
    'hevc': 'libx265',
    'av1': 'libaom-av1',
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
        self.audio_stream = self.get_audio_stream()
        self.video_input_codec = self.video_stream['codec_name']
        self.audio_input_codec = self.audio_stream['codec_name']
        self.video_color = get_video_color(self.video_stream)
        self.video_color_bit_depth = get_video_color_bit_depth(self.video_stream)
        self.can_copy_video = self.get_can_copy_video()
        self.can_copy_audio = self.get_can_copy_audio()
        self.video_output_codec_lib = None
        self.audio_output_codec_lib = None
        self.video_output_codec = (
            self.video_input_codec
            if self.can_copy_video
            else self.settings.transcode_video_codec
        )
        self.audio_output_codec = (
            self.audio_input_codec
            if self.can_copy_audio
            else self.settings.transcode_audio_codec
        )
        self.ffmpeg_args = None
        self.transcode_folder = None

    async def start(self, send_data_callback=None) -> bool | bytes:
        self.transcode_folder = self.create_transcode_folder()

        await self.set_ffmpeg_args()

        args = to_subprocess_arguments(self.ffmpeg_args)
        logger.debug(f'[{self.settings.session}] FFmpeg start args: {" ".join(args)}')
        self.process = await asyncio.create_subprocess_exec(
            os.path.join(config.ffmpeg_folder, 'ffmpeg'),
            *args,
            env=subprocess_env(self.settings.session, 'transcode'),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self.register_session()

        logger.debug(f'[{self.settings.session}] Waiting for media')
        ready = False
        try:
            ready = await asyncio.wait_for(
                self.wait_for_media(), timeout=60 if not config.debug else 20
            )
        except asyncio.TimeoutError:
            logger.error(
                f'[{self.settings.session}] Failed to create media, gave up waiting'
            )
            try:
                self.process.terminate()
            except Exception:
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
        if self.settings.session in sessions:
            close_transcoder(self.settings.session)
            logger.info(f'[{self.settings.session}] Reregistered')
            sessions[self.settings.session].process = self.process
            sessions[self.settings.session].call_later.cancel()
            sessions[self.settings.session].call_later = loop.call_later(
                config.session_timeout, close_session_callback, self.settings.session
            )
        else:
            logger.info(f'[{self.settings.session}] Registered')
            sessions[self.settings.session] = Session_model(
                process=self.process,
                transcode_folder=self.transcode_folder,
                call_later=loop.call_later(
                    config.session_timeout,
                    close_session_callback,
                    self.settings.session,
                ),
            )

    async def set_ffmpeg_args(self):
        self.ffmpeg_args = [
            {'-analyzeduration': '200M'},
        ]
        if self.can_copy_video:
            self.ffmpeg_args.append({'-fflags': '+genpts'})
        self.set_hardware_decoder()
        if self.settings.start_time:
            self.ffmpeg_args.append(
                {'-ss': str(self.settings.start_time.quantize(Decimal('0.000')))}
            )
        self.ffmpeg_args.extend(
            [
                {'-i': f"file:{self.metadata['format']['filename']}"},
                {'-map_metadata': '-1'},
                {'-map_chapters': '-1'},
                {'-threads': '0'},
                {'-max_delay': '5000000'},
                {'-max_muxing_queue_size': '2048'},
            ]
        )
        self.set_video()
        self.set_audio()
        self.ffmpeg_extend_args()

    def set_hardware_decoder(self):
        if not config.ffmpeg_hwaccel_enabled:
            return

        if self.can_copy_video:
            return

        if config.ffmpeg_hwaccel == 'qsv':
            self.ffmpeg_args.extend(
                [
                    {'-init_hw_device': 'vaapi=va:'},
                    {'-init_hw_device': 'qsv=qs@va'},
                    {'-filter_hw_device': 'qs'},
                    {'-hwaccel': 'vaapi'},
                    {'-hwaccel_output_format': 'vaapi'},
                ]
            )

        elif config.ffmpeg_hwaccel == 'vaapi':
            self.ffmpeg_args.extend(
                [
                    {'-init_hw_device': f'vaapi=va:{config.ffmpeg_hwaccel_device}'},
                    {'-hwaccel': 'vaapi'},
                    {'-hwaccel_output_format': 'vaapi'},
                ]
            )

    def set_video(self):
        codec = codecs_to_library.get(self.video_output_codec, self.video_output_codec)

        if self.can_copy_video:
            codec = 'copy'
            if self.settings.start_time > 0:
                i = self.find_ffmpeg_arg_index('-ss')
                # Audio goes out of sync if not used
                self.ffmpeg_args.insert(i + 1, {'-noaccurate_seek': None})

            self.ffmpeg_args.extend(
                [
                    {'-start_at_zero': None},
                    {'-avoid_negative_ts': 'disabled'},
                    {'-copyts': None},
                ]
            )
        else:
            if config.ffmpeg_hwaccel_enabled:
                codec = f'{self.settings.transcode_video_codec}_{config.ffmpeg_hwaccel}'

        self.video_output_codec_lib = codec
        self.ffmpeg_args.extend(
            [
                {'-map': '0:v:0'},
                {'-c:v': codec},
            ]
        )

        if self.video_output_codec == 'hevc':
            if (
                self.can_copy_video
                and self.video_color.range_type == 'dovi'
                and self.video_stream.get('codec_tag_string')
                in ('dovi', 'dvh1', 'dvhe')
            ):
                self.ffmpeg_args.append({'-tag:v': 'dvh1'})
                self.ffmpeg_args.append({'-strict': '2'})
            else:
                self.ffmpeg_args.append({'-tag:v': 'hvc1'})

        if codec == 'copy':
            return

        width = self.settings.max_width or self.video_stream['width']
        if width > self.video_stream['width']:
            width = self.video_stream['width']

        if config.ffmpeg_hwaccel_enabled:
            self.ffmpeg_args.append({'-autoscale': '0'})
            if config.ffmpeg_hwaccel_low_powermode:
                self.ffmpeg_args.append({'-low_power': '1'})
            if self.settings.transcode_video_codec == 'hevc':
                # Fails with "Error while filtering: Cannot allocate memory" if not added
                self.ffmpeg_args.append({'-async_depth': '1'})

        vf = self.get_video_filter(width)
        if vf:
            self.ffmpeg_args.append({'-vf': ','.join(vf)})
        self.ffmpeg_args.extend(self.get_quality_params(width, codec))

    def get_can_copy_video(self, check_key_frames=True):
        if self.settings.force_transcode:
            logger.debug(f'[{self.settings.session}] Force transcode enabled')
            return False

        if self.video_input_codec not in self.settings.supported_video_codecs:
            logger.debug(
                f'[{self.settings.session}] Input codec not supported by client: {self.video_input_codec}'
            )
            return False

        if (
            self.settings.supported_video_color_bit_depth
            and self.video_color_bit_depth
            > int(self.settings.supported_video_color_bit_depth)
        ):
            logger.debug(
                f'[{self.settings.session}] Video color bit depth not supported by client: {self.video_color_bit_depth}'
            )
            return False

        if (
            self.video_color.range == 'hdr'
            and self.video_color.range_type not in self.settings.supported_hdr_formats
            and config.ffmpeg_tonemap_enabled
        ):
            logger.debug(
                f'[{self.settings.session}] HDR format not supported by client: {self.video_color.range_type}'
            )
            return False

        if (
            self.settings.max_width
            and self.settings.max_width < self.video_stream['width']
        ):
            logger.debug(
                f'[{self.settings.session}] Requested width is lower than input width ({self.settings.max_width} < {self.video_stream["width"]})'
            )
            return False

        if self.settings.max_video_bitrate and self.settings.max_video_bitrate < int(
            self.metadata['format']['bit_rate'] or 0
        ):
            logger.debug(
                f'[{self.settings.session}] Requested max bitrate is lower than input bitrate ({self.settings.max_video_bitrate} < {self.get_video_transcode_bitrate()})'
            )
            return False

        # We need the key frames to determin the actually start time when seeking
        # otherwise the subtitles will be out of sync
        if check_key_frames and not self.metadata.get('keyframes'):
            logger.debug(f'[{self.settings.session}] No key frames in metadata')
            return False

        logger.debug(f'[{self.settings.session}] Can copy video')
        return True

    def get_can_device_direct_play(self):
        if not self.get_can_copy_video(check_key_frames=False):
            return False

        if not any(
            fmt in self.settings.supported_video_containers
            for fmt in self.metadata['format']['format_name'].split(',')
        ):
            logger.debug(
                f'[{self.settings.session}] Input video container not supported: {self.metadata["format"]["format_name"]}'
            )
            return False
        if not self.settings.client_can_switch_audio_track:
            # It's possible that multiple audio streams are marked as default :)
            default_count = 0
            for stream in self.metadata['streams']:
                if stream['codec_type'] == 'audio':
                    if stream.get('disposition', {}).get('default'):
                        default_count += 1

            if not self.audio_stream.get('disposition', {}).get('default') or (
                default_count > 1
            ):
                if self.audio_stream['group_index'] != 0:
                    logger.debug(
                        f"[{self.settings.session}] Client can't switch audio track"
                    )
                    return False

        logger.debug(f'[{self.settings.session}] Can direct play video')
        return True

    def get_video_filter(self, width: int):
        vf = []
        if self.video_color_bit_depth <= self.settings.supported_video_color_bit_depth:
            pix_fmt = self.video_stream['pix_fmt']
        else:
            pix_fmt = (
                'yuv420p'
                if self.settings.supported_video_color_bit_depth == 8
                else 'yuv420p10le'
            )

        tonemap = (
            self.video_color.range_type not in self.settings.supported_hdr_formats
            and self.can_tonemap()
        )

        if tonemap or (
            self.video_color.range == 'hdr'
            and self.video_color.range_type in self.settings.supported_hdr_formats
        ):
            vf.append(
                'setparams=color_primaries=bt2020:color_trc=smpte2084:colorspace=bt2020nc'
            )
        else:
            vf.append(
                'setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709'
            )

        if not config.ffmpeg_hwaccel_enabled:
            if width:
                vf.append(f'scale=width={width}:height=-2')
            vf.append(f'format={pix_fmt}')
            # missing software tonemap
            return

        if pix_fmt == 'yuv420p10le':
            if self.video_output_codec_lib == 'h264_qsv':
                pix_fmt = 'yuv420p'

        format_ = ''
        if not tonemap:
            if pix_fmt == 'yuv420p10le':
                format_ = 'format=p010le'
            else:
                format_ = 'format=nv12'

        width_filter = (
            f'w={width}:h=-2'
            if (width != self.video_stream['width'])
            or (
                self.video_input_codec == 'av1'
            )  # [av1 @ 0x64e783171840] HW accel start frame fail. - Add the width.
            else ''
        )
        if width_filter and format_:
            format_ = ':' + format_

        if width_filter or pix_fmt != self.video_stream['pix_fmt']:
            if config.ffmpeg_hwaccel == 'qsv':
                vf.append(f'scale_vaapi={width_filter}{format_}')
            else:
                vf.append(f'scale_{config.ffmpeg_hwaccel}={width_filter}{format_}')
            if not tonemap:
                vf.append(
                    f'hwmap=derive_device={config.ffmpeg_hwaccel},format={config.ffmpeg_hwaccel}'
                )

        if tonemap:
            vf.extend(self.get_tonemap_hardware_filter())

        return vf

    def get_tonemap_hardware_filter(self):
        if config.ffmpeg_hwaccel in ('qsv', 'vaapi'):
            qsv_extra = ':extra_hw_frames=16' if config.ffmpeg_hwaccel == 'qsv' else ''
            if self.video_color.range_type == 'hdr10':
                return [
                    'tonemap_vaapi=format=nv12:p=bt709:t=bt709:m=bt709',
                    f'procamp_vaapi=b=0:c=1.2{qsv_extra}',
                    f'hwmap=derive_device={config.ffmpeg_hwaccel}',
                    f'format={config.ffmpeg_hwaccel}',
                ]
            if self.video_color.range_type == 'dovi':
                return [
                    'hwmap=derive_device=opencl',
                    'tonemap_opencl=format=nv12:p=bt709:t=bt709:m=bt709:tonemap=bt2390:peak=100:desat=0',
                    f'hwmap=derive_device={config.ffmpeg_hwaccel}:reverse=1{qsv_extra}',
                    f'format={config.ffmpeg_hwaccel}',
                ]
        return []

    def can_tonemap(self):
        if self.video_color_bit_depth != 10 or not config.ffmpeg_tonemap_enabled:
            return False

        if (
            self.video_input_codec == 'hevc'
            and self.video_color.range == 'hdr'
            and self.video_color.range_type == 'dovi'
        ):
            return config.ffmpeg_hwaccel in ('qsv', 'vaapi')

        return self.video_color.range == 'hdr' and (
            self.video_color.range_type in ('hdr10', 'hlg')
        )

    def get_quality_params(self, width: int, codec_library: str):
        params = []
        params.append({'-preset': config.ffmpeg_preset})
        if codec_library == 'libx264':
            params.append(
                {
                    '-x264opts': 'subme=0:me_range=4:rc_lookahead=10:me=hex:8x8dct=0:partitions=none'
                }
            )
            if width >= 3840:
                params.append({'-crf': 18})
            elif width >= 1920:
                params.append({'-crf': 19})
            else:
                params.append({'-crf': 26})

        elif codec_library == 'libx265':
            params.extend(
                [
                    {'-x265-params:0': 'no-info=1'},
                ]
            )
            if width >= 3840:
                params.append({'-crf': 18})
            elif width >= 3840:
                params.append({'-crf': 20})
            elif width >= 1920:
                params.append({'-crf': 22})
            else:
                params.append({'-crf': 31})

        elif codec_library == 'libvpx-vp9':
            params.append({'-g': '24'})
            if width >= 3840:
                params.append({'-crf': 15})
            elif width >= 2560:
                params.append({'-crf': 24})
            elif width >= 1920:
                params.append({'-crf': 31})
            else:
                params.append({'-crf': 34})

        elif codec_library == 'h264_qsv':
            params.append({'-look_ahead': '0'})

        params.extend(self.get_video_bitrate_params(codec_library))
        return params

    def set_audio(self):
        stream = self.audio_stream
        codec = codecs_to_library.get(stream['codec_name'], '')

        # Audio goes out of sync if audio copy is used while the video is being transcoded
        if self.can_copy_video and self.can_copy_audio:
            codec = 'copy'
        else:
            if not codec or codec not in self.settings.supported_audio_codecs:
                codec = codecs_to_library.get(self.settings.transcode_audio_codec, '')
            bitrate = stream.get('bit_rate', stream['channels'] * 128000)
            if (
                self.settings.max_audio_channels
                and self.settings.max_audio_channels < stream['channels']
            ):
                bitrate = self.settings.max_audio_channels * 128000
                self.ffmpeg_args.append({'-ac': self.settings.max_audio_channels})
            else:
                self.ffmpeg_args.append({'-ac': stream['channels']})
            self.ffmpeg_args.append({'-b:a': bitrate})
        if not codec:
            raise Exception('No audio codec library')
        self.audio_output_codec_lib = codec
        self.ffmpeg_args.extend(
            [
                {'-map': f'0:{stream["index"]}'},
                {'-c:a': codec},
            ]
        )

    def get_can_copy_audio(self):
        stream = self.audio_stream

        if (
            self.settings.max_audio_channels
            and self.settings.max_audio_channels < stream['channels']
        ):
            logger.debug(
                f'[{self.settings.session}] Requested audio channels is lower than input channels ({self.settings.max_audio_channels} < {stream["channels"]})'
            )
            return False

        if stream['codec_name'] not in self.settings.supported_audio_codecs:
            logger.debug(
                f'[{self.settings.session}] Input audio codec not supported: {stream["codec_name"]}'
            )
            return False

        logger.debug(
            f'[{self.settings.session}] Can copy audio, codec: {stream["codec_name"]}'
        )
        return True

    def get_video_bitrate_params(self, codec_library: str):
        bitrate = self.get_video_transcode_bitrate()

        if codec_library in ('libx264', 'libx265', 'libvpx-vp9'):
            return [
                {'-maxrate': bitrate},
                {'-bufsize': bitrate * 2},
            ]

        return [
            {'-b:v': bitrate},
            {'-maxrate': bitrate},
            {'-bufsize': bitrate * 2},
        ]

    def get_video_bitrate(self):
        if self.can_copy_video:
            return int(self.metadata['format']['bit_rate'] or 0)
        else:
            return self.get_video_transcode_bitrate()

    def get_video_transcode_bitrate(self):
        bitrate = self.settings.max_video_bitrate or int(
            self.metadata['format']['bit_rate'] or 0
        )

        if bitrate:
            upscaling = (
                self.settings.max_width
                and self.settings.max_width > self.video_stream['width']
            )
            # only allow bitrate increase if upscaling
            if not upscaling:
                bitrate = self._min_video_bitrate(
                    int(self.metadata['format']['bit_rate']), bitrate
                )

            bitrate = self._video_scale_bitrate(
                bitrate, self.video_input_codec, self.settings.transcode_video_codec
            )

            # don't exceed the requested bitrate
            if self.settings.max_video_bitrate:
                bitrate = min(bitrate, self.settings.max_video_bitrate)

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
            return 0.6
        if codec == 'av1':
            return 0.5
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

    def get_audio_stream(self):
        index = self.stream_index_by_lang('audio', self.settings.audio_lang)
        self.metadata['streams'][index.index]['group_index'] = index.group_index
        return self.metadata['streams'][index.index]

    def find_ffmpeg_arg(self, key):
        for a in self.ffmpeg_args:
            if key in a:
                return a[key]

    def change_ffmpeg_arg(self, key, new_value):
        for a in self.ffmpeg_args:
            if key in a:
                a[key] = new_value
                break

    def find_ffmpeg_arg_index(self, key):
        for i, a in enumerate(self.ffmpeg_args):
            if key in a:
                return i

    def create_transcode_folder(self):
        transcode_folder = os.path.join(config.transcode_folder, self.settings.session)
        if not os.path.exists(transcode_folder):
            os.makedirs(transcode_folder)
        return transcode_folder

    def segment_time(self):
        return 6 if self.get_can_copy_video() else 3


def subprocess_env(session, type_):
    env = {}
    env['FFREPORT'] = (
        f'file=\'{os.path.join(config.transcode_folder, f"ffmpeg_{session}_{type_}.log")}\':level={config.ffmpeg_loglevel}'
    )
    return env


def to_subprocess_arguments(args):
    l = []
    for a in args:
        for key, value in a.items():
            l.append(key)
            if value:
                l.append(str(value))
    return l


def get_video_stream(metadata: dict):
    for stream in metadata['streams']:
        if stream['codec_type'] == 'video':
            return stream
    raise Exception('No video stream')


def get_video_color(source: dict):
    if (
        source.get('color_transfer') == 'smpte2084'
        and source.get('color_primaries') == 'bt2020'
    ):
        return Video_color(range='hdr', range_type='hdr10')

    if source.get('color_transfer') == 'arib-std-b67':
        return Video_color(range='hdr', range_type='hlg')

    if source.get('codec_tag_string') in ('dovi', 'dvh1', 'dvhe', 'dav1'):
        return Video_color(range='hdr', range_type='dovi')

    if source.get('side_data_list'):
        for s in source['side_data_list']:
            if (
                s.get('dv_profile') in (5, 7, 8)
                and s.get('rpu_present_flag')
                and s.get('bl_present_flag')
                and s.get('dv_bl_signal_compatibility_id') in (0, 1, 4)
            ):
                return Video_color(range='hdr', range_type='dovi')

    return Video_color(range='sdr', range_type='sdr')


def get_video_color_bit_depth(source: dict):
    pix_fmt = source['pix_fmt']
    if pix_fmt in ('yuv420p10le', 'yuv444p10le'):
        return 10
    if pix_fmt in ('yuv420p12le', 'yuv444p12le'):
        return 12
    return 8


def stream_index_by_lang(metadata: Dict, codec_type: str, lang: str):
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
            if lang == '' and stream.get('disposition', {}).get('default'):
                return Stream_index(index=i, group_index=group_index)
            if 'tags' in stream and lang:
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
    logger.debug(f'[{session}] Session timeout reached')
    close_session(session)


def close_session(session):
    if session not in sessions:
        logger.info(f'[{session}] Already closed')
        return
    logger.info(f'[{session}] Closing')
    close_transcoder(session)
    s = sessions[session]
    try:
        if s.transcode_folder:
            if os.path.exists(s.transcode_folder):
                shutil.rmtree(s.transcode_folder)
            else:
                logger.warning(
                    f"[{session}] Path: {s.transcode_folder} not found, can't delete it"
                )
    except:
        pass
    s.call_later.cancel()
    del sessions[session]


def close_transcoder(session):
    try:
        sessions[session].process.kill()
    except:
        pass
