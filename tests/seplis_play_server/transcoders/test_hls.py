from seplis_play_server.testbase import run_file
from seplis_play_server.transcoders.hls import Hls_transcoder
from seplis_play_server.transcoders.video import Transcode_settings

def test_hls():
    settings = Transcode_settings(
        play_id='a',
        session='123',
        supported_video_codecs=['h264'],
        supported_audio_codecs=['aac'],
        transcode_video_codec='h264',
        transcode_audio_codec='aac',
        format='hls',
    )
    metadata = {
        "streams": [
            {
                "index": 0,
                "codec_name": "hevc",
                "codec_long_name": "H.265 / HEVC (High Efficiency Video Coding)",
                "profile": "Main 10",
                "codec_type": "video",
                "codec_tag_string": "[0][0][0][0]",
                "codec_tag": "0x0000",
                "width": 1920,
                "height": 1080,
                "coded_width": 1920,
                "coded_height": 1080,
                "has_b_frames": 2,
                "sample_aspect_ratio": "1:1",
                "display_aspect_ratio": "16:9",
                "pix_fmt": "yuv420p10le",
                "level": 120,
                "color_range": "tv",
                "chroma_location": "left",
                "r_frame_rate": "24000/1001",
                "avg_frame_rate": "24000/1001",            
            },
            {
                "index": 1,
                "codec_name": "aac",
                "codec_type": "audio",
                "sample_rate": "48000",
                "channels": 6,
            }
        ],
        "format": {
            "format_name": "matroska,webm",
            "format_long_name": "Matroska / WebM",
            "start_time": "0.000000",
            "duration": "3486.590000",
            "size": "2743430123",
            "bit_rate": "6294815",
            "probe_score": 100,
        },
        "keyframes": [
            "0.000000",
            "6.715000",
            "10.761000",
            "14.473000",
            "24.900000",
            "25.984000",
            "27.819000",
            "30.489000",
            "31.865000",
            "33.200000",
            "36.787000",
            "38.455000",
            "41.208000",
            "44.002000",
            "46.505000",
            "48.757000",
            "50.634000",
            "56.723000",
            "60.352000",
            "62.562000",
            "68.527000",
            "75.909000",
            "86.336000",
            "90.882000",
            "92.384000",
            "96.221000",
        ]
    }

    hls = Hls_transcoder(settings, metadata)

if __name__ == '__main__':
    run_file(__file__)