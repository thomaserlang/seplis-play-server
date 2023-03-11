# from https://github.com/dbr/tvnamer/blob/master/tvnamer/config_defaults.py
SERIES_FILENAME_PATTERNS = [
    # [group] Show - 01-02 [crc]
    '''^\[(?P<group>.+?)\][ ]?               # group name, captured for [#100]
    (?P<file_title>.*?)[ ]?[-_][ ]?          # show name, padding, spaces?
    (?P<numberstart>\d+)              # first episode number
    ([-_]\d+)*                               # optional repeating episodes
    [-_](?P<numberend>\d+)            # last episode number
    (?=                                      # Optional group for crc value (non-capturing)
      .*                                     # padding
      \[(?P<crc>.+?)\]                       # CRC value
    )?                                       # End optional crc group
    [^\/]*$''',

    # [group] Show - 01 [crc]
    '''^\[(?P<group>.+?)\][ ]?               # group name, captured for [#100]
    (?P<file_title>.*)                       # show name
    [ ]?[-_][ ]?                             # padding and seperator
    (?P<number>\d+)                   # episode number
    (?=                                      # Optional group for crc value (non-capturing)
      .*                                     # padding
      \[(?P<crc>.+?)\]                       # CRC value
    )?                                       # End optional crc group
    [^\/]*$''',

    # foo s01e23 s01e24 s01e25 *
    '''
    ^((?P<file_title>.+?)[ \._\-])?          # show name
    [Ss](?P<season>[0-9]+)             # s01
    [\.\- ]?                                 # separator
    [Ee](?P<numberstart>[0-9]+)       # first e23
    ([\.\- ]+                                # separator
    [Ss](?P=season)                    # s01
    [\.\- ]?                                 # separator
    [Ee][0-9]+)*                             # e24 etc (middle groups)
    ([\.\- ]+                                # separator
    [Ss](?P=season)                    # last s01
    [\.\- ]?                                 # separator
    [Ee](?P<numberend>[0-9]+))        # final episode number
    [^\/]*$''',

    # foo.s01e23e24*
    '''
    ^((?P<file_title>.+?)[ \._\-])?          # show name
    [Ss](?P<season>[0-9]+)             # s01
    [\.\- ]?                                 # separator
    [Ee](?P<numberstart>[0-9]+)       # first e23
    ([\.\- ]?                                # separator
    [Ee][0-9]+)*                             # e24e25 etc
    [\.\- ]?[Ee](?P<numberend>[0-9]+) # final episode num
    [^\/]*$''',

    # foo.1x23 1x24 1x25
    '''
    ^((?P<file_title>.+?)[ \._\-])?          # show name
    (?P<season>[0-9]+)                 # first season number (1)
    [xX](?P<numberstart>[0-9]+)       # first episode (x23)
    ([ \._\-]+                               # separator
    (?P=season)                        # more season numbers (1)
    [xX][0-9]+)*                             # more episode numbers (x24)
    ([ \._\-]+                               # separator
    (?P=season)                        # last season number (1)
    [xX](?P<numberend>[0-9]+))        # last episode number (x25)
    [^\/]*$''',

    # foo.1x23x24*
    '''
    ^((?P<file_title>.+?)[ \._\-])?          # show name
    (?P<season>[0-9]+)                 # 1
    [xX](?P<numberstart>[0-9]+)       # first x23
    ([xX][0-9]+)*                            # x24x25 etc
    [xX](?P<numberend>[0-9]+)         # final episode num
    [^\/]*$''',

    # foo.s01e23-24*
    '''
    ^((?P<file_title>.+?)[ \._\-])?          # show name
    [Ss](?P<season>[0-9]+)             # s01
    [\.\- ]?                                 # separator
    [Ee](?P<numberstart>[0-9]+)       # first e23
    (                                        # -24 etc
         [\-]
         [Ee]?[0-9]+
    )*
         [\-]                                # separator
         [Ee]?(?P<numberend>[0-9]+)   # final episode num
    [\.\- ]                                  # must have a separator (prevents s01e01-720p from being 720 episodes)
    [^\/]*$''',

    # foo.1x23-24*
    '''
    ^((?P<file_title>.+?)[ \._\-])?          # show name
    (?P<season>[0-9]+)                 # 1
    [xX](?P<numberstart>[0-9]+)       # first x23
    (                                        # -24 etc
         [\-+][0-9]+
    )*
         [\-+]                               # separator
         (?P<numberend>[0-9]+)        # final episode num
    ([\.\-+ ].*                              # must have a separator (prevents 1x01-720p from being 720 episodes)
    |
    $)''',

    # foo.[1x09-11]*
    '''^(?P<file_title>.+?)[ \._\-]          # show name and padding
    \[                                       # [
        ?(?P<season>[0-9]+)            # season
    [xX]                                     # x
        (?P<numberstart>[0-9]+)       # episode
        ([\-+] [0-9]+)*
    [\-+]                                    # -
        (?P<numberend>[0-9]+)         # episode
    \]                                       # \]
    [^\\/]*$''',

    # foo - [012]
    '''^((?P<file_title>.+?)[ \._\-])?       # show name and padding
    \[                                       # [ not optional (or too ambigious)
    (?P<number>[0-9]+)                # episode
    \]                                       # ]
    [^\\/]*$''',
    # foo.s0101, foo.0201
    '''^(?P<file_title>.+?)[ \._\-]
    [Ss](?P<season>[0-9]{2})
    [\.\- ]?
    (?P<number>[0-9]{2})
    [^0-9]*$''',

    # foo.1x09*
    '''^((?P<file_title>.+?)[ \._\-])?       # show name and padding
    \[?                                      # [ optional
    (?P<season>[0-9]+)                 # season
    [xX]                                     # x
    (?P<number>[0-9]+)                # episode
    \]?                                      # ] optional
    [^\\/]*$''',

    # foo.s01.e01, foo.s01_e01, "foo.s01 - e01"
    '''^((?P<file_title>.+?)[ \._\-])?
    \[?
    [Ss](?P<season>[0-9]+)[ ]?[\._\- ]?[ ]?
    [Ee]?(?P<number>[0-9]+)
    \]?
    [^\\/]*$''',

    # foo.2010.01.02.etc
    '''
    ^((?P<file_title>.+?)[ \._\-])?          # show name
    (?P<year>\d{4})                          # year
    [ \._\-]                                 # separator
    (?P<month>\d{2})                         # month
    [ \._\-]                                 # separator
    (?P<day>\d{2})                           # day
    [^\/]*$''',

    # foo - [01.09]
    '''^((?P<file_title>.+?))                # show name
    [ \._\-]?                                # padding
    \[                                       # [
    (?P<season>[0-9]+?)                # season
    [.]                                      # .
    (?P<number>[0-9]+?)               # episode
    \]                                       # ]
    [ \._\-]?                                # padding
    [^\\/]*$''',

    # Foo - S2 E 02 - etc
    '''^(?P<file_title>.+?)[ ]?[ \._\-][ ]?
    [Ss](?P<season>[0-9]+)[\.\- ]?
    [Ee]?[ ]?(?P<number>[0-9]+)
    [^\\/]*$''',

    # Show - Episode 9999 [S 12 - Ep 131] - etc
    '''
    (?P<file_title>.+)                       # Showname
    [ ]-[ ]                                  # -
    [Ee]pisode[ ]\d+                         # Episode 1234 (ignored)
    [ ]
    \[                                       # [
    [sS][ ]?(?P<season>\d+)            # s 12
    ([ ]|[ ]-[ ]|-)                          # space, or -
    ([eE]|[eE]p)[ ]?(?P<number>\d+)   # e or ep 12
    \]                                       # ]
    .*$                                      # rest of file
    ''',

    # show name 2 of 6 - blah
    '''^(?P<file_title>.+?)                  # Show name
    [ \._\-]                                 # Padding
    (?P<number>[0-9]+)                # 2
    of                                       # of
    [ \._\-]?                                # Padding
    \d+                                      # 6
    ([\._ -]|$|[^\\/]*$)                     # More padding, then anything
    ''',

    # Show.Name.Part.1.and.Part.2
    '''(?i)^
    (?P<file_title>.+?)                        # Show name
    [ \._\-]                                   # Padding
    (?:part|pt)?[\._ -]
    (?P<numberstart>[0-9]+)             # Part 1
    (?:
      [ \._-](?:and|&|to)                        # and
      [ \._-](?:part|pt)?                        # Part 2
      [ \._-](?:[0-9]+))*                        # (middle group, optional, repeating)
    [ \._-](?:and|&|to)                        # and
    [ \._-]?(?:part|pt)?                       # Part 3
    [ \._-](?P<numberend>[0-9]+)        # last episode number, save it
    [\._ -][^\\/]*$                            # More padding, then anything
    ''',

    # Show.Name.Part1
    '''^(?P<file_title>.+?)                  # Show name\n
    [ \\._\\-]                               # Padding\n
    [Pp]art[ ](?P<number>[0-9]+)      # Part 1\n
    [\\._ -][^\\/]*$                         # More padding, then anything\n
    ''',

    # show name Season 01 Episode 20
    '''^(?P<file_title>.+?)[ ]?               # Show name
    [Ss]eason[ ]?(?P<season>[0-9]+)[ ]? # Season 1
    [Ee]pisode[ ]?(?P<number>[0-9]+)   # Episode 20
    [^\\/]*$''',                              # Anything

    # foo.103*
    '''^(?P<file_title>.+)[ \._\-]
    (?P<number>[0-9]+)
    [\._ -][^\\/]*$''',

    # foo.0103*
    '''^(?P<file_title>.+)[ \._\-]
    (?P<season>[0-9]{2})
    (?P<number>[0-9]{2,3})
    [\._ -][^\\/]*$''',

    # show.name.e123.abc
    '''^(?P<file_title>.+?)                  # Show name
    [ \._\-]                                 # Padding
    [Ee](?P<number>[0-9]+)            # E123
    [\._ -][^\\/]*$                          # More padding, then anything
    ''',
]

SCAN_TYPES = (
    'series',
    'movies',
)