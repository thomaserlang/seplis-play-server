import asyncio
import os
import shutil
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from loguru import logger
from pydantic import (
    BaseModel,
    ConfigDict,
)

from seplis_play import config
from seplis_play.ffmpeg.ffmpeg_runner import FFmpegRunner
from seplis_play.schemas.source_metadata_schemas import (
    SourceMetadata,
    SourceMetadataAudioStream,
    SourceMetadataVideoStream,
)
from seplis_play.schemas.source_schemas import Source, SourceStream
from seplis_play.transcoding.transcode_decision_schema import (
    BlockerCode,
    DecisionBlocker,
    DecisionCheck,
    DecisionScope,
    DirectPlayDecision,
    LimitKind,
    PlaybackMethod,
    StreamAction,
    StreamDecision,
    StreamKind,
    TranscodeDecision,
    format_blocker,
)
from seplis_play.transcoding.transcode_settings_schema import TranscodeSettings


class VideoColor(BaseModel):
    range: str
    range_type: str


@dataclass
class SessionModel:
    ffmpeg_runner: FFmpegRunner
    call_later: asyncio.TimerHandle
    transcode_folder: str | None = None
    segment_time: int = 0
    transcode_decision: TranscodeDecision | None = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


sessions: dict[str, SessionModel] = {}

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


class StreamIndex(BaseModel):
    index: int
    group_index: int


class Transcoder:
    def __init__(self, settings: TranscodeSettings, metadata: SourceMetadata) -> None:
        self.settings = settings
        self.metadata = metadata
        self.source = Source.from_source_metadata(
            metadata=metadata,
            index=settings.source_index,
        )
        self.video_stream = self.get_video_stream()
        self.audio_stream = self.get_audio_stream()
        self.video_input_codec = self.video_stream['codec_name']
        self.audio_input_codec = self.audio_stream['codec_name']
        self.video_color = get_video_color(self.video_stream)
        self.video_color_bit_depth = get_video_color_bit_depth(self.video_stream)
        self.video_copy_decision = self.evaluate_can_copy_video()
        self.can_copy_video = self.video_copy_decision.supported
        self.audio_copy_decision = self.evaluate_can_copy_audio()
        self.can_copy_audio = self.audio_copy_decision.supported
        self.direct_play_decision = self.evaluate_can_device_direct_play()
        self.transcode_decision = self.build_transcode_decision()
        store_transcode_decision(self.transcode_decision)
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
        self.ffmpeg_args: list[Mapping[str, str | float | int | None]] = []
        self.transcode_folder = ''
        self.ffmpeg_runner = FFmpegRunner()

    async def start(self) -> bool | bytes:
        self.transcode_folder = self.create_transcode_folder()

        await self.set_ffmpeg_args()

        args = [
            os.path.join(config.ffmpeg_folder, 'ffmpeg'),
            *to_subprocess_arguments(self.ffmpeg_args),
        ]

        try:
            self.process = await self.ffmpeg_runner.start(
                args,
                source=self.source,
            )
            if not self.process:
                return False
        except RuntimeError as e:
            logger.error(f'[{self.settings.session}] {e}')
            return False

        await self.register_session()

        return True

    def ffmpeg_extend_args(self) -> None:
        pass

    def ffmpeg_change_args(self) -> None:
        pass

    async def wait_for_media(self) -> bool:
        return True

    def close(self) -> None:
        pass

    @property
    def media_path(self) -> str:
        raise NotImplementedError()

    @property
    def media_name(self) -> str:
        raise NotImplementedError()

    async def register_session(self) -> None:
        loop = asyncio.get_event_loop()
        if self.settings.session in sessions:
            await close_transcoder(self.settings.session)
            logger.info(f'[{self.settings.session}] Reregistered')
            sessions[self.settings.session].ffmpeg_runner = self.ffmpeg_runner
            sessions[self.settings.session].transcode_decision = self.transcode_decision
            sessions[self.settings.session].call_later.cancel()
            sessions[self.settings.session].call_later = loop.call_later(
                config.session_timeout, close_session_callback, self.settings.session
            )
        else:
            logger.info(f'[{self.settings.session}] Registered')
            sessions[self.settings.session] = SessionModel(
                ffmpeg_runner=self.ffmpeg_runner,
                transcode_folder=self.transcode_folder,
                call_later=loop.call_later(
                    config.session_timeout,
                    close_session_callback,
                    self.settings.session,
                ),
                transcode_decision=self.transcode_decision,
            )

    async def set_ffmpeg_args(self) -> None:
        self.ffmpeg_args = [
            {'-analyzeduration': '200M'},
        ]
        if self.can_copy_video:
            self.ffmpeg_args.append({'-fflags': '+genpts'})
        self.set_hardware_decoder()
        if self.settings.start_time:
            t = self.settings.start_time
            ss = f'{int(t // 3600):02d}:{int((t % 3600) // 60):02d}:{float(t % 60):06.3f}'
            self.ffmpeg_args.append({'-ss': ss})
        self.ffmpeg_args.extend(
            [
                {'-i': f'file:{self.metadata["format"]["filename"]}'},
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

    def set_hardware_decoder(self) -> None:
        if not config.ffmpeg_hwaccel_enabled:
            return

        if self.can_copy_video:
            return

        if config.ffmpeg_hwaccel == 'qsv':
            self.ffmpeg_args.extend(
                [
                    {'-init_hw_device': f'vaapi=va:{config.ffmpeg_hwaccel_device}'},
                    {'-init_hw_device': 'qsv=qs@va'},
                    {'-filter_hw_device': 'qs'},
                    {'-hwaccel': 'vaapi'},
                    {'-hwaccel_output_format': 'vaapi'},
                    {'-noautorotate': None},
                ]
            )
        else:
            raise NotImplementedError(
                f'Unsupported hwaccel: {config.ffmpeg_hwaccel} '
                f'only supports qsv currently'
            )

    def set_video(self) -> None:
        codec = codecs_to_library.get(self.video_output_codec, self.video_output_codec)

        if self.can_copy_video:
            codec = 'copy'
            if self.settings.start_time > 0:
                i = self.find_ffmpeg_arg_index('-ss')
                if not i:
                    logger.error(
                        f'[{self.settings.session}] Failed to find -ss in ffmpeg args'
                    )
                    return
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
            if self.settings.start_time > 0:
                t = self.settings.start_time
                h, m, s = int(t // 3600), int((t % 3600) // 60), float(t % 60)
                ts = f'{h:02d}:{m:02d}:{s:06.3f}'
                self.ffmpeg_args.append({'-output_ts_offset': ts})

        self.video_output_codec_lib = codec
        self.ffmpeg_args.extend(
            [
                {'-map': '0:v:0'},
                {'-map': '-0:s'},
                {'-c:v': codec},
            ]
        )

        if self.video_output_codec == 'hevc':
            if (
                self.can_copy_video
                and self.video_color.range_type == 'dovi'
                and self.video_stream.get('codec_tag_string') in ('dovi', 'dvh1', 'dvhe')
            ):
                self.ffmpeg_args.append({'-tag:v': 'dvh1'})
                self.ffmpeg_args.append({'-strict': '2'})
            else:
                self.ffmpeg_args.append({'-tag:v': 'hvc1'})

        if codec == 'copy':
            return

        width = self.get_output_width()

        if config.ffmpeg_hwaccel_enabled:
            self.ffmpeg_args.append({'-noautoscale': None})
            if config.ffmpeg_hwaccel_low_powermode:
                self.ffmpeg_args.append({'-low_power': '1'})
            if self.settings.transcode_video_codec == 'hevc':
                # Fails with "Error while filtering: Cannot allocate memory" if not added
                self.ffmpeg_args.append({'-async_depth': '1'})

        vf = self.get_video_filter(width)
        if vf:
            self.ffmpeg_args.append({'-vf': ','.join(vf)})
        self.ffmpeg_args.extend(self.get_quality_params(width, codec))

    def get_output_width(self) -> int:
        width = self.settings.max_width or self.video_stream['width']
        if width > self.video_stream['width']:
            width = self.video_stream['width']
        return width

    def get_output_resolution(self) -> tuple[int, int]:
        width = self.get_output_width()
        if width != self.video_stream['width']:
            return (
                width,
                round(self.video_stream['height'] * width / self.video_stream['width']),
            )
        return (self.video_stream['width'], self.video_stream['height'])

    def evaluate_can_copy_video(self, check_key_frames: bool = True) -> DecisionCheck:
        if self.settings.force_transcode:
            return DecisionCheck(
                supported=False,
                blockers=[
                    DecisionBlocker(
                        code=BlockerCode.FORCED,
                        scope=DecisionScope.VIDEO,
                        stream=StreamKind.VIDEO,
                        source_codec=self.video_input_codec,
                        target_codec=self.settings.transcode_video_codec,
                    )
                ],
            )

        if self.video_input_codec not in self.settings.supported_video_codecs:
            return DecisionCheck(
                supported=False,
                blockers=[
                    DecisionBlocker(
                        code=BlockerCode.UNSUPPORTED_CODEC,
                        scope=DecisionScope.VIDEO,
                        stream=StreamKind.VIDEO,
                        source_codec=self.video_input_codec,
                        supported=tuple(self.settings.supported_video_codecs),
                    )
                ],
            )

        if (
            self.settings.supported_video_color_bit_depth
            and self.video_color_bit_depth
            > int(self.settings.supported_video_color_bit_depth)
        ):
            return DecisionCheck(
                supported=False,
                blockers=[
                    DecisionBlocker(
                        code=BlockerCode.LIMIT_EXCEEDED,
                        scope=DecisionScope.VIDEO,
                        stream=StreamKind.VIDEO,
                        limit_kind=LimitKind.VIDEO_BIT_DEPTH,
                        limit=self.settings.supported_video_color_bit_depth,
                        actual=self.video_color_bit_depth,
                    )
                ],
            )

        if (
            self.video_color.range == 'hdr'
            and self.video_color.range_type not in self.settings.supported_hdr_formats
            and config.ffmpeg_tonemap_enabled
        ):
            return DecisionCheck(
                supported=False,
                blockers=[
                    DecisionBlocker(
                        code=BlockerCode.UNSUPPORTED_HDR,
                        scope=DecisionScope.VIDEO,
                        stream=StreamKind.VIDEO,
                        source_hdr=self.video_color.range_type,
                        supported=tuple(self.settings.supported_hdr_formats),
                    )
                ],
            )

        if (
            self.settings.max_width
            and self.settings.max_width < self.video_stream['width']
        ):
            return DecisionCheck(
                supported=False,
                blockers=[
                    DecisionBlocker(
                        code=BlockerCode.LIMIT_EXCEEDED,
                        scope=DecisionScope.VIDEO,
                        stream=StreamKind.VIDEO,
                        limit_kind=LimitKind.WIDTH,
                        limit=self.settings.max_width,
                        actual=self.video_stream['width'],
                    )
                ],
            )

        if (
            self.settings.max_video_bitrate
            and self.settings.max_video_bitrate < self.source.bitrate
        ):
            return DecisionCheck(
                supported=False,
                blockers=[
                    DecisionBlocker(
                        code=BlockerCode.LIMIT_EXCEEDED,
                        scope=DecisionScope.VIDEO,
                        stream=StreamKind.VIDEO,
                        limit_kind=LimitKind.VIDEO_BITRATE,
                        limit=self.settings.max_video_bitrate,
                        actual=self.source.bitrate,
                    )
                ],
            )

        # We need the key frames to determin the actually start time when seeking
        # otherwise the subtitles will be out of sync
        if check_key_frames and not self.metadata.get('keyframes'):
            return DecisionCheck(
                supported=False,
                blockers=[
                    DecisionBlocker(
                        code=BlockerCode.MISSING_KEYFRAMES,
                        scope=DecisionScope.VIDEO,
                        stream=StreamKind.VIDEO,
                    )
                ],
            )

        return DecisionCheck(
            supported=True,
            blockers=[],
        )

    def get_can_copy_video(self, check_key_frames: bool = True) -> bool:
        decision = (
            self.video_copy_decision
            if check_key_frames
            else self.evaluate_can_copy_video(check_key_frames=False)
        )
        log_decision_check(self.settings.session, 'video copy', decision)
        return decision.supported

    def evaluate_can_device_direct_play(self) -> DecisionCheck:
        video_copy = self.evaluate_can_copy_video(check_key_frames=False)
        if not video_copy.supported:
            return DecisionCheck(
                supported=False,
                blockers=[
                    DecisionBlocker(
                        code=BlockerCode.UNSUPPORTED_CODEC,
                        scope=DecisionScope.PLAYBACK,
                        stream=StreamKind.VIDEO,
                        source_codec=self.video_input_codec,
                    ),
                    *video_copy.blockers,
                ],
            )

        if not self.audio_copy_decision.supported:
            return DecisionCheck(
                supported=False,
                blockers=[
                    DecisionBlocker(
                        code=BlockerCode.UNSUPPORTED_CODEC,
                        scope=DecisionScope.PLAYBACK,
                        stream=StreamKind.AUDIO,
                        source_codec=self.audio_input_codec,
                    ),
                    *self.audio_copy_decision.blockers,
                ],
            )

        if not any(
            fmt in self.settings.supported_video_containers
            for fmt in self.metadata['format']['format_name'].split(',')
        ):
            return DecisionCheck(
                supported=False,
                blockers=[
                    DecisionBlocker(
                        code=BlockerCode.UNSUPPORTED_CONTAINER,
                        scope=DecisionScope.CONTAINER,
                        source_container=self.metadata['format']['format_name'],
                        supported=tuple(self.settings.supported_video_containers),
                    )
                ],
            )

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
                if self.audio_stream.get('group_index', 0) != 0:
                    return DecisionCheck(
                        supported=False,
                        blockers=[
                            DecisionBlocker(
                                code=BlockerCode.AUDIO_TRACK_SWITCH_UNSUPPORTED,
                                scope=DecisionScope.PLAYBACK,
                                stream=StreamKind.AUDIO,
                            )
                        ],
                    )

        return DecisionCheck(
            supported=True,
            blockers=[],
        )

    def get_can_device_direct_play(self) -> bool:
        log_decision_check(
            self.settings.session, 'direct play', self.direct_play_decision
        )
        return self.direct_play_decision.supported

    def build_transcode_decision(self) -> TranscodeDecision:
        video_transcode_required = not self.can_copy_video
        audio_transcode_required = not (self.can_copy_video and self.can_copy_audio)
        needs_transcode = video_transcode_required or audio_transcode_required
        audio_decision = self.audio_copy_decision
        if not self.can_copy_video:
            audio_decision = DecisionCheck(
                supported=False,
                blockers=[
                    DecisionBlocker(
                        code=BlockerCode.VIDEO_TRANSCODE_REQUIRES_AUDIO_TRANSCODE,
                        scope=DecisionScope.AUDIO,
                        stream=StreamKind.AUDIO,
                        source_codec=self.audio_input_codec,
                        target_codec=self.settings.transcode_audio_codec,
                    )
                ],
            )

        method: PlaybackMethod
        if self.direct_play_decision.supported:
            method = PlaybackMethod.DIRECT_PLAY
        elif needs_transcode:
            method = PlaybackMethod.TRANSCODE
        else:
            method = PlaybackMethod.REMUX

        video_action: StreamAction = (
            StreamAction.TRANSCODE
            if video_transcode_required
            else StreamAction.COPY
        )
        audio_action: StreamAction = (
            StreamAction.TRANSCODE
            if audio_transcode_required
            else StreamAction.COPY
        )

        return TranscodeDecision(
            session=self.settings.session,
            method=method,
            required=needs_transcode,
            video=StreamDecision(
                kind=StreamKind.VIDEO,
                action=video_action,
                source_codec=self.video_input_codec,
                target_codec=(
                    self.settings.transcode_video_codec
                    if video_transcode_required
                    else self.video_input_codec
                ),
                blockers=tuple(self.video_copy_decision.blockers),
            ),
            audio=StreamDecision(
                kind=StreamKind.AUDIO,
                action=audio_action,
                source_codec=self.audio_input_codec,
                target_codec=(
                    self.settings.transcode_audio_codec
                    if audio_transcode_required
                    else self.audio_input_codec
                ),
                blockers=tuple(audio_decision.blockers),
            ),
            direct_play=DirectPlayDecision(
                supported=self.direct_play_decision.supported,
                blockers=tuple(self.direct_play_decision.blockers),
            ),
        )

    def get_video_filter(self, width: int) -> list[str] | None:
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
            vf.append('setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709')

        if not config.ffmpeg_hwaccel_enabled:
            if width:
                vf.append(f'scale=width={width}:height=-2')
            vf.append(f'format={pix_fmt}')
            # missing software tonemap
            return None

        if pix_fmt == 'yuv420p10le':
            if self.video_output_codec_lib == 'h264_qsv':
                pix_fmt = 'yuv420p'

        scale_filter_options = []
        if (width != self.video_stream['width']) or (
            self.video_input_codec == 'av1'
        ):  # [av1 @ 0x64e783171840] HW accel start frame fail. - Add the width.
            scale_filter_options.extend([f'w={width}', 'h=-2'])

        if not tonemap:
            if pix_fmt == 'yuv420p10le':
                scale_filter_options.append('format=p010le')
            else:
                scale_filter_options.append('format=nv12')

        if config.ffmpeg_hwaccel == 'qsv':
            scale_filter_options.append('extra_hw_frames=24')
            scale_filter = 'scale_vaapi'
        else:
            scale_filter = f'scale_{config.ffmpeg_hwaccel}'

        if scale_filter_options:
            scale_filter += f'={":".join(scale_filter_options)}'
        vf.append(scale_filter)

        if not tonemap:
            vf.append(
                f'hwmap=derive_device={config.ffmpeg_hwaccel},format={config.ffmpeg_hwaccel}'
            )
        else:
            vf.extend(self.get_tonemap_hardware_filter())

        return vf

    def get_tonemap_hardware_filter(self) -> list[str]:
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

    def can_tonemap(self) -> bool:
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

    def get_quality_params(
        self, width: int, output_codec: str
    ) -> list[Mapping[str, str]]:
        params = []
        params.append({'-preset': config.ffmpeg_preset})
        match output_codec:
            case 'libx264':
                params.append(
                    {
                        '-x264opts': (
                            'subme=0:me_range=4:rc_lookahead=10:me=hex:8x8dct=0:partitions=none'
                        )
                    }
                )
                if width >= 3840:
                    params.append({'-crf': 18})
                elif width >= 1920:
                    params.append({'-crf': 19})
                else:
                    params.append({'-crf': 26})

            case 'libx265':
                params.append(
                    {'-x265-params:0': 'no-info=1'},
                )
                if width >= 3840:
                    params.append({'-crf': 18})
                elif width >= 3840:
                    params.append({'-crf': 20})
                elif width >= 1920:
                    params.append({'-crf': 22})
                else:
                    params.append({'-crf': 31})

            case 'libvpx-vp9':
                params.append({'-g': '24'})
                if width >= 3840:
                    params.append({'-crf': 15})
                elif width >= 2560:
                    params.append({'-crf': 24})
                elif width >= 1920:
                    params.append({'-crf': 31})
                else:
                    params.append({'-crf': 34})

            case 'h264_qsv':
                params.append({'-look_ahead': '0'})

            case _:
                pass

        params.extend(self.get_video_bitrate_params(output_codec))
        return params

    def set_audio(self) -> None:
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

    def evaluate_can_copy_audio(self) -> DecisionCheck:
        stream = self.audio_stream

        if (
            self.settings.max_audio_channels
            and self.settings.max_audio_channels < stream['channels']
        ):
            return DecisionCheck(
                supported=False,
                blockers=[
                    DecisionBlocker(
                        code=BlockerCode.LIMIT_EXCEEDED,
                        scope=DecisionScope.AUDIO,
                        stream=StreamKind.AUDIO,
                        limit_kind=LimitKind.AUDIO_CHANNELS,
                        limit=self.settings.max_audio_channels,
                        actual=stream['channels'],
                    )
                ],
            )

        if stream['codec_name'] not in self.settings.supported_audio_codecs:
            return DecisionCheck(
                supported=False,
                blockers=[
                    DecisionBlocker(
                        code=BlockerCode.UNSUPPORTED_CODEC,
                        scope=DecisionScope.AUDIO,
                        stream=StreamKind.AUDIO,
                        source_codec=stream['codec_name'],
                        supported=tuple(self.settings.supported_audio_codecs),
                    )
                ],
            )

        return DecisionCheck(
            supported=True,
            blockers=[],
        )

    def get_can_copy_audio(self) -> bool:
        log_decision_check(self.settings.session, 'audio copy', self.audio_copy_decision)
        return self.audio_copy_decision.supported

    def get_video_bitrate_params(
        self, codec_library: str
    ) -> list[Mapping[str, str | int | float]]:
        bitrate = self.get_video_transcode_bitrate()

        if codec_library in ('libx264', 'libx265', 'libvpx-vp9'):
            return [
                {'-maxrate': bitrate},
                {'-bufsize': bitrate * 2},
            ]

        if codec_library in ('h264_qsv', 'hevc_qsv', 'av1_qsv'):
            params = []
            if codec_library in ('h264_qsv', 'hevc_qsv'):
                params.append({'-mbbrc': 1})
            max_int = 2**31 - 1
            params += [
                {'-b:v': bitrate},
                {'-maxrate': min(bitrate + 1, max_int)},
                {'-rc_init_occupancy': min(bitrate * 2, max_int)},
                {'-bufsize': min(bitrate * 4, max_int)},
            ]
            return params

        return [
            {'-b:v': bitrate},
            {'-maxrate': bitrate},
            {'-bufsize': bitrate * 2},
        ]

    def get_video_bitrate(self) -> int:
        if self.can_copy_video:
            return self.source.bitrate
        return self.get_video_transcode_bitrate()

    def get_video_transcode_bitrate(self) -> int:
        bitrate = self.settings.max_video_bitrate or self.source.bitrate

        if bitrate:
            upscaling = (
                self.settings.max_width
                and self.settings.max_width > self.video_stream['width']
            )
            # only allow bitrate increase if upscaling
            if not upscaling:
                bitrate = self._min_video_bitrate(self.source.bitrate, bitrate)

            bitrate = self._video_scale_bitrate(
                bitrate, self.video_input_codec, self.settings.transcode_video_codec
            )

            if self.settings.max_video_bitrate:
                bitrate = min(bitrate, self.settings.max_video_bitrate)

        # Make sure when calculating the bufsize (bitrate * 2)
        # that it doesn't exceed the maxsize
        return int(min(bitrate or 0, sys.maxsize / 2))

    def _min_video_bitrate(self, input_bitrate: int, requested_bitrate: int) -> int:
        bitrate = input_bitrate
        if bitrate <= 2000000:
            bitrate = int(bitrate * 2.5)
        elif bitrate <= 3000000:
            bitrate *= 2
        return min(bitrate, requested_bitrate)

    def _video_bitrate_scale_factor(self, codec: str) -> float:
        if codec in ('hevc', 'vp9'):
            return 0.6
        if codec == 'av1':
            return 0.5
        return 1

    def _video_scale_bitrate(
        self, bitrate: int, input_codec: str, output_codec: str
    ) -> int:
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

    def stream_by_lang(
        self, streams: list[SourceStream], lang: str | None
    ) -> SourceStream | None:
        return stream_by_lang(streams, lang)

    def get_video_stream(self) -> SourceMetadataVideoStream:
        return get_video_stream(self.metadata)

    def get_audio_stream(self) -> SourceMetadataAudioStream:
        stream = self.stream_by_lang(self.source.audio, self.settings.audio_lang)
        if stream is None and self.source.audio:
            stream = self.source.audio[0]
        if stream is None:
            raise Exception('No audio stream')
        stream_metadata = self.metadata['streams'][stream.index]
        if stream_metadata['codec_type'] != 'audio':
            raise Exception('Selected stream is not audio')
        return stream_metadata

    def find_ffmpeg_arg(self, key: str) -> str | int | float | None:
        for a in self.ffmpeg_args:
            if key in a:
                return a[key]
        return None

    def change_ffmpeg_arg(self, key: str, new_value: str | int | float) -> None:
        for a in self.ffmpeg_args:
            if key in a:
                a[key] = new_value  # type: ignore
                break

    def find_ffmpeg_arg_index(self, key: str) -> int | None:
        for i, a in enumerate(self.ffmpeg_args):
            if key in a:
                return i
        return None

    def create_transcode_folder(self) -> str:
        transcode_folder = os.path.join(config.transcode_folder, self.settings.session)
        if not os.path.exists(transcode_folder):
            os.makedirs(transcode_folder)
        return transcode_folder

    def segment_time(self) -> int:
        return 6 if self.get_can_copy_video() else 3


def to_subprocess_arguments(
    args: Sequence[Mapping[str, str | int | float | None]],
) -> list[str]:
    arguments = []
    for a in args:
        for key, value in a.items():
            arguments.append(key)
            if value is not None:
                arguments.append(f'{value}')
    return arguments


def get_video_stream(metadata: SourceMetadata) -> SourceMetadataVideoStream:
    for stream in metadata['streams']:
        if stream['codec_type'] == 'video':
            return stream
    raise Exception('No video stream')


def get_video_color(stream: SourceMetadataVideoStream) -> VideoColor:
    if (
        stream.get('color_transfer') == 'smpte2084'
        and stream.get('color_primaries') == 'bt2020'
    ):
        return VideoColor(range='hdr', range_type='hdr10')

    if stream.get('color_transfer') == 'arib-std-b67':
        return VideoColor(range='hdr', range_type='hlg')

    if stream.get('codec_tag_string') in ('dovi', 'dvh1', 'dvhe', 'dav1'):
        return VideoColor(range='hdr', range_type='dovi')

    side_data_list = stream.get('side_data_list')
    if side_data_list:
        for s in side_data_list:
            if (
                s.get('dv_profile') in (5, 7, 8)
                and s.get('rpu_present_flag')
                and s.get('bl_present_flag')
                and s.get('dv_bl_signal_compatibility_id') in (0, 1, 4)
            ):
                return VideoColor(range='hdr', range_type='dovi')

    return VideoColor(range='sdr', range_type='sdr')


def get_video_color_bit_depth(stream: SourceMetadataVideoStream) -> int:
    pix_fmt = stream['pix_fmt']
    if pix_fmt in ('yuv420p10le', 'yuv444p10le'):
        return 10
    if pix_fmt in ('yuv420p12le', 'yuv444p12le'):
        return 12
    return 8


def stream_by_lang(streams: list[SourceStream], lang: str | None) -> SourceStream | None:
    logger.debug(f'Looking for stream with language {lang}')
    langs = []
    lang = '' if lang is None else lang
    group_index = None
    if ':' in lang:
        lang, group_index = lang.split(':')
        if not group_index.isdigit():
            logger.warning(f'Invalid group index: {group_index}')
            group_index = None

        group_index = int(group_index or 0)
        stream = next(
            (stream for stream in streams if stream.group_index == group_index), None
        )
        if not stream or (stream.language and stream.language.lower() != lang.lower()):
            group_index = None

    for stream in streams:
        if lang == '' and stream.default:
            return stream
        if not stream.language:
            continue
        langs.append(stream.language)
        if (
            not group_index or stream.group_index == group_index
        ) and stream.language.lower() == lang.lower():
            return stream
    logger.warning(f'Found no stream with language: {lang}')
    logger.warning(f'Available streams: {", ".join(langs)}')
    return None


def close_session_callback(session: str) -> None:
    logger.debug(f'[{session}] Session timeout reached')
    _ = asyncio.create_task(close_session(session))


async def close_session(session: str) -> None:
    if session not in sessions:
        logger.info(f'[{session}] Already closed')
        return
    logger.info(f'[{session}] Closing')
    await close_transcoder(session)
    s = sessions[session]
    try:
        if s.transcode_folder:
            if os.path.exists(s.transcode_folder):
                shutil.rmtree(s.transcode_folder)
            else:
                logger.warning(
                    f"[{session}] Path: {s.transcode_folder} not found, can't delete it"
                )
    except Exception as e:
        logger.error(f'[{session}] Failed to delete transcode folder: {e}')
    s.call_later.cancel()
    del sessions[session]


async def close_transcoder(session: str) -> None:
    try:
        await sessions[session].ffmpeg_runner.cancel()
    except Exception as e:
        logger.error(f'[{session}] Failed to cancel transcoder: {e}')


def log_decision_check(session: str, label: str, decision: DecisionCheck) -> None:
    status = 'supported' if decision.supported else 'blocked'
    logger.debug(
        f'[{session}] {label}: {status} '
        f'({", ".join(format_blocker(blocker) for blocker in decision.blockers)})'
    )


def summarize_transcode_decision(decision: TranscodeDecision) -> str:
    direct_play_status = 'yes' if decision.direct_play.supported else 'no'
    direct_play_blockers = ', '.join(
        format_blocker(blocker) for blocker in decision.direct_play.blockers
    )
    return (
        f'method={decision.method} | '
        f'video={decision.video.action} '
        f'({decision.video.source_codec} -> {decision.video.target_codec}; '
        f'{", ".join(format_blocker(blocker) for blocker in decision.video.blockers)}) | '
        f'audio={decision.audio.action} '
        f'({decision.audio.source_codec} -> {decision.audio.target_codec}; '
        f'{", ".join(format_blocker(blocker) for blocker in decision.audio.blockers)}) | '
        f'direct_play={direct_play_status} ({direct_play_blockers})'
    )


def store_transcode_decision(decision: TranscodeDecision) -> None:
    previous = sessions.get(decision.session)
    if previous and previous.transcode_decision == decision:
        return
    logger.info(
        f'[{decision.session}] Transcode decision: '
        f'{summarize_transcode_decision(decision)}'
    )
