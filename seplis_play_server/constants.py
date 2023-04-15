# from https://github.com/dbr/tvnamer/blob/master/tvnamer/config_defaults.py
SERIES_FILENAME_PATTERNS = [
    # [group] Show - 01-02 [crc]
    r'''^\[(?P<group>.+?)\][ ]?              # group name, captured for [#100]
    (?P<file_title>.*?)[ ]?[-_][ ]?          # show name, padding, spaces?
    (?P<episode_start>\d+)                   # first episode number
    ([-_]\d+)*                               # optional repeating episodes
    [-_](?P<episode_end>\d+)                 # last episode number
    (?=                                      # Optional group for crc value (non-capturing)
      .*                                     # padding
      \[(?P<crc>.+?)\]                       # CRC value
    )?                                       # End optional crc group
    [^\/]*$''',

    # [group] Show - 01 [crc]
    r'''^\[(?P<group>.+?)\][ ]?              # group name, captured for [#100]
    (?P<file_title>.*)                       # show name
    [ ]?[-_][ ]?                             # padding and seperator
    (?P<absolute_number>\d+)                 # episode number
    (?=                                      # Optional group for crc value (non-capturing)
      .*                                     # padding
      \[(?P<crc>.+?)\]                       # CRC value
    )?                                       # End optional crc group
    [^\/]*$''',

    # foo s01e23 s01e24 s01e25 *
    r'''
    ^((?P<file_title>.+?)[ \._\-])?          # show name
    [Ss](?P<season>[0-9]+)             # s01
    [\.\- ]?                                 # separator
    [Ee](?P<episode_start>[0-9]+)       # first e23
    ([\.\- ]+                                # separator
    [Ss](?P=season)                    # s01
    [\.\- ]?                                 # separator
    [Ee][0-9]+)*                             # e24 etc (middle groups)
    ([\.\- ]+                                # separator
    [Ss](?P=season)                    # last s01
    [\.\- ]?                                 # separator
    [Ee](?P<episode_end>[0-9]+))        # final episode number
    [^\/]*$''',

    # foo.s01e23e24*
    r'''
    ^((?P<file_title>.+?)[ \._\-])?          # show name
    [Ss](?P<season>[0-9]+)                   # s01
    [\.\- ]?                                 # separator
    [Ee](?P<episode_start>[0-9]+)            # first e23
    ([\.\- ]?                                # separator
    [Ee][0-9]+)*                             # e24e25 etc
    [\.\- ]?[Ee](?P<episode_end>[0-9]+) # final episode num
    [^\/]*$''',

    # foo.1x23 1x24 1x25
    r'''
    ^((?P<file_title>.+?)[ \._\-])?          # show name
    (?P<season>[0-9]+)                 # first season number (1)
    [xX](?P<episode_start>[0-9]+)       # first episode (x23)
    ([ \._\-]+                               # separator
    (?P=season)                        # more season numbers (1)
    [xX][0-9]+)*                             # more episode numbers (x24)
    ([ \._\-]+                               # separator
    (?P=season)                        # last season number (1)
    [xX](?P<episode_end>[0-9]+))        # last episode number (x25)
    [^\/]*$''',

    # foo.1x23x24*
    r'''
    ^((?P<file_title>.+?)[ \._\-])?          # show name
    (?P<season>[0-9]+)                 # 1
    [xX](?P<episode_start>[0-9]+)       # first x23
    ([xX][0-9]+)*                            # x24x25 etc
    [xX](?P<episode_end>[0-9]+)         # final episode num
    [^\/]*$''',

    # foo.s01e23-24*
    r'''
    ^((?P<file_title>.+?)[ \._\-])?          # show name
    [Ss](?P<season>[0-9]+)             # s01
    [\.\- ]?                                 # separator
    [Ee](?P<episode_start>[0-9]+)       # first e23
    (                                        # -24 etc
         [\-]
         [Ee]?[0-9]+
    )*
         [\-]                                # separator
         [Ee]?(?P<episode_end>[0-9]+)   # final episode num
    [\.\- ]                                  # must have a separator (prevents s01e01-720p from being 720 episodes)
    [^\/]*$''',

    # foo.1x23-24*
    r'''
    ^((?P<file_title>.+?)[ \._\-])?          # show name
    (?P<season>[0-9]+)                 # 1
    [xX](?P<episode_start>[0-9]+)       # first x23
    (                                        # -24 etc
         [\-+][0-9]+
    )*
         [\-+]                               # separator
         (?P<episode_end>[0-9]+)        # final episode num
    ([\.\-+ ].*                              # must have a separator (prevents 1x01-720p from being 720 episodes)
    |
    $)''',

    # foo.s0101, foo.0201
    r'''^(?P<file_title>.+?)[ ]?[ \._\-][ ]?
    [Ss](?P<season>[0-9]{2})
    [\.\- ]?
    (?P<episode>[0-9]{2})
    [^0-9]*$''',

    # foo.1x09*
    r'''^((?P<file_title>.+?)[ \._\-])?       # show name and padding
    \[?                                      # [ optional
    (?P<season>[0-9]+)                 # season
    [xX]                                     # x
    (?P<episode>[0-9]+)                # episode
    \]?                                      # ] optional
    [^\\/]*$''',

    # foo.s01.e01, foo.s01_e01, "foo.s01 - e01"
    r'''^(?P<file_title>.+?)[ ]?[ \._\-][ ]?
    \[?
    [Ss](?P<season>[0-9]+)[ ]?[\._\- ]?[ ]?
    [Ee]?(?P<episode>[0-9]+)
    \]?
    [^\\/]*$''',

    # foo.2010.01.02.etc
    r'''
    ^((?P<file_title>.+?)[ \._\-])?          # show name
    (?P<year>\d{4})                          # year
    [ \._\-]                                 # separator
    (?P<month>\d{2})                         # month
    [ \._\-]                                 # separator
    (?P<day>\d{2})                           # day
    [^\/]*$''',

    # Foo - S2 E 02 - etc
    r'''^(?P<file_title>.+?)[ ]?[ \._\-][ ]?
    [Ss](?P<season>[0-9]+)[\.\- ]?
    [Ee]?[ ]?(?P<episode>[0-9]+)
    [^\\/]*$''',

    # show name Season 01 Episode 20
    r'''^(?P<file_title>.+?)[ ]?        # Show name
    [Ss]eason[ ]?(?P<season>[0-9]+)[ ]? # Season 1
    [Ee]pisode[ ]?(?P<episode>[0-9]+)   # Episode 20
    [^\/]*$''',                         # Anything

    # foo.103*
    r'''^(?P<file_title>.+?)[ ]?[ \._\-][ ]?
    (?P<absolute_number>[0-9]+)
    [\._ -][^\\/]*$''',

    # foo.0103*
    r'''^(?P<file_title>.+)[ \._\-]
    (?P<season>[0-9]{2})
    (?P<episode>[0-9]{2,3})
    [\._ -][^\\/]*$''',

    # show.name.e123.abc
    r'''^(?P<file_title>.+?)                 # Show name
    [ \._\-]                                 # Padding
    [Ee](?P<absolute_number>[0-9]+)          # E123
    [\._ -][^\\/]*$                          # More padding, then anything
    ''',
]

SCAN_TYPES = (
    'series',
    'movies',
)