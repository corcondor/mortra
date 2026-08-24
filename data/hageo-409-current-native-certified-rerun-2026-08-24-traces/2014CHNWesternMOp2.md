# 2014CHNWesternMOp2: Yuclid proof trace

- Certificate: `data/hageo-409-current-native-certified-rerun-2026-08-24-runs/proofs/2014CHNWesternMOp2.json`
- Deductions read: 109
- Order: Yuclid certificate order; every deduction is retained.

## Complete deduction trace

### D000 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,p,c,p)

### D001 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,p,o,p)

### D002 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(b,q,d,q)

### D003 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,o,c,o)

### D004 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,o,d,o)

### D005 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(b,q,o,q)

### D006 `construction`

Dependencies: none

Assumptions: none

Assertions:
- midp(o,a,b)

### D007 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(c,q,b,d,p,a)

### D008 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(q,b,c,p,a,d)

### D009 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,p,c,p,a,p,c,p)

### D010 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(c,p,a,a,c,p)

### D011 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(b,q,d,q,b,q,d,q)

### D012 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(d,q,b,b,d,q)

### D013 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(c,d,o,d,o,c)

### D014 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(c,o,d,o,c,o,d,o)

### D015 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(d,o,c,c,d,o)

### D016 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,o,c,o,a,o,c,o)

### D017 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(a,o,c,c,a,o)

### D018 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(c,p,o,a,o,p)

### D019 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(o,c,p,o,p,a)

### D020 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(c,p,o,o,p,a)

### D021 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(a,d,o,d,o,a)

### D022 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,o,d,o,a,o,d,o)

### D023 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(d,o,a,a,d,o)

### D024 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(o,b,q,b,q,o)

### D025 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(b,q,o,q,b,q,o,q)

### D026 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(b,q,o,o,b,q)

### D027 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(o,d,q,d,q,o)

### D028 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(d,q,o,q,d,q,o,q)

### D029 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(d,q,o,o,d,q)

### D030 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,o)

### D031 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,b)

### D032 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,o)

### D033 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(b,c,d)

### D034 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,c,d)

### D035 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,c,o)

### D036 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,d,o)

### D037 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,o,p)

### D038 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,b,q)

### D039 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,d,q)

### D040 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,o,q)

### D041 `ar:ratio chasing:squared_distance`

Dependencies: D000

Assumptions:
- cong(a,p,c,p): (1/1)*|a-p|^2 + (-1/1)*|c-p|^2 = 0

Assertions:
- eqratio(a,p,c,p,c,p,a,p): (2/1)*|a-p|^2 + (-2/1)*|c-p|^2 = 0

### D042 `dd:r63`

Dependencies: D041, D009, D010

Assumptions:
- eqratio(a,p,c,p,c,p,a,p)
- eqangle(a,p,c,p,a,p,c,p)
- sameclock(c,p,a,a,c,p)

Assertions:
- simtrir(a,c,p,c,a,p)

### D043 `dd:r53`

Dependencies: D042, D010

Assumptions:
- simtrir(a,c,p,c,a,p)
- sameclock(c,p,a,a,c,p)

Assertions:
- eqangle(a,c,c,p,a,p,a,c)

### D044 `ar:ratio chasing:squared_distance`

Dependencies: D002

Assumptions:
- cong(b,q,d,q): (1/1)*|b-q|^2 + (-1/1)*|d-q|^2 = 0

Assertions:
- eqratio(b,q,d,q,d,q,b,q): (2/1)*|b-q|^2 + (-2/1)*|d-q|^2 = 0

### D045 `dd:r63`

Dependencies: D044, D011, D012

Assumptions:
- eqratio(b,q,d,q,d,q,b,q)
- eqangle(b,q,d,q,b,q,d,q)
- sameclock(d,q,b,b,d,q)

Assertions:
- simtrir(b,d,q,d,b,q)

### D046 `dd:r53`

Dependencies: D045, D012

Assumptions:
- simtrir(b,d,q,d,b,q)
- sameclock(d,q,b,b,d,q)

Assertions:
- eqangle(b,d,d,q,b,q,b,d)

### D047 `ar:ratio chasing:squared_distance`

Dependencies: D003, D004

Assumptions:
- cong(a,o,c,o): (1/1)*|a-o|^2 + (-1/1)*|c-o|^2 = 0
- cong(a,o,d,o): (1/1)*|a-o|^2 + (-1/1)*|d-o|^2 = 0

Assertions:
- eqratio(c,o,d,o,d,o,c,o): (2/1)*|c-o|^2 + (-2/1)*|d-o|^2 = 0

### D048 `dd:r63`

Dependencies: D047, D014, D015

Assumptions:
- eqratio(c,o,d,o,d,o,c,o)
- eqangle(c,o,d,o,c,o,d,o)
- sameclock(d,o,c,c,d,o)

Assertions:
- simtrir(c,d,o,d,c,o)

### D049 `dd:r53`

Dependencies: D048, D013

Assumptions:
- simtrir(c,d,o,d,c,o)
- sameclock(c,d,o,d,o,c)

Assertions:
- eqangle(c,d,d,o,c,o,c,d)

### D050 `ar:ratio chasing:squared_distance`

Dependencies: D003

Assumptions:
- cong(a,o,c,o): (1/1)*|a-o|^2 + (-1/1)*|c-o|^2 = 0

Assertions:
- eqratio(a,o,c,o,c,o,a,o): (2/1)*|a-o|^2 + (-2/1)*|c-o|^2 = 0

### D051 `dd:r63`

Dependencies: D050, D016, D017

Assumptions:
- eqratio(a,o,c,o,c,o,a,o)
- eqangle(a,o,c,o,a,o,c,o)
- sameclock(a,o,c,c,a,o)

Assertions:
- simtrir(a,c,o,c,a,o)

### D052 `dd:r53`

Dependencies: D051, D017

Assumptions:
- simtrir(a,c,o,c,a,o)
- sameclock(a,o,c,c,a,o)

Assertions:
- eqangle(a,c,c,o,a,o,a,c)

### D053 `ar:ratio chasing:squared_distance`

Dependencies: D000, D003

Assumptions:
- cong(a,p,c,p): (1/1)*|a-p|^2 + (-1/1)*|c-p|^2 = 0
- cong(a,o,c,o): (1/1)*|a-o|^2 + (-1/1)*|c-o|^2 = 0

Assertions:
- eqratio(a,o,a,p,c,o,c,p): (1/1)*|a-o|^2 + (-1/1)*|a-p|^2 + (-1/1)*|c-o|^2 + (1/1)*|c-p|^2 = 0

### D054 `ar:angle chasing:directed_angle`

Dependencies: D043, D052

Assumptions:
- eqangle(a,c,c,p,a,p,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-p) + (1/1)*∠(c-p) = 0
- eqangle(a,c,c,o,a,o,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-o) + (1/1)*∠(c-o) = 0

Assertions:
- eqangle(a,o,a,p,c,p,c,o): (-1/1)*∠(a-o) + (1/1)*∠(a-p) + (-1/1)*∠(c-o) + (1/1)*∠(c-p) = 0

### D055 `dd:r63`

Dependencies: D053, D054, D019

Assumptions:
- eqratio(a,o,a,p,c,o,c,p)
- eqangle(a,o,a,p,c,p,c,o)
- sameclock(o,c,p,o,p,a)

Assertions:
- simtrir(a,o,p,c,o,p)

### D056 `dd:r53`

Dependencies: D055, D018

Assumptions:
- simtrir(a,o,p,c,o,p)
- sameclock(c,p,o,a,o,p)

Assertions:
- eqangle(a,p,o,p,o,p,c,p)

### D057 `ar:ratio chasing:squared_distance`

Dependencies: D000, D001

Assumptions:
- cong(a,p,c,p): (1/1)*|a-p|^2 + (-1/1)*|c-p|^2 = 0
- cong(a,p,o,p): (1/1)*|a-p|^2 + (-1/1)*|o-p|^2 = 0

Assertions:
- eqratio(a,p,o,p,o,p,c,p): (1/1)*|a-p|^2 + (1/1)*|c-p|^2 + (-2/1)*|o-p|^2 = 0

### D058 `dd:r62`

Dependencies: D057, D056, D020

Assumptions:
- eqratio(a,p,o,p,o,p,c,p)
- eqangle(a,p,o,p,o,p,c,p)
- sameclock(c,p,o,o,p,a)

Assertions:
- simtri(a,o,p,o,c,p)

### D059 `dd:r52`

Dependencies: D058, D020

Assumptions:
- simtri(a,o,p,o,c,p)
- sameclock(c,p,o,o,p,a)

Assertions:
- eqangle(c,o,o,p,a,o,a,p)

### D060 `ar:ratio chasing:squared_distance`

Dependencies: D004

Assumptions:
- cong(a,o,d,o): (1/1)*|a-o|^2 + (-1/1)*|d-o|^2 = 0

Assertions:
- eqratio(a,o,d,o,d,o,a,o): (2/1)*|a-o|^2 + (-2/1)*|d-o|^2 = 0

### D061 `dd:r63`

Dependencies: D060, D022, D023

Assumptions:
- eqratio(a,o,d,o,d,o,a,o)
- eqangle(a,o,d,o,a,o,d,o)
- sameclock(d,o,a,a,d,o)

Assertions:
- simtrir(a,d,o,d,a,o)

### D062 `dd:r53`

Dependencies: D061, D021

Assumptions:
- simtrir(a,d,o,d,a,o)
- sameclock(a,d,o,d,o,a)

Assertions:
- eqangle(a,d,d,o,a,o,a,d)

### D063 `ar:ratio chasing:squared_distance`

Dependencies: D005

Assumptions:
- cong(b,q,o,q): (1/1)*|b-q|^2 + (-1/1)*|o-q|^2 = 0

Assertions:
- eqratio(b,q,o,q,o,q,b,q): (2/1)*|b-q|^2 + (-2/1)*|o-q|^2 = 0

### D064 `dd:r63`

Dependencies: D063, D025, D026

Assumptions:
- eqratio(b,q,o,q,o,q,b,q)
- eqangle(b,q,o,q,b,q,o,q)
- sameclock(b,q,o,o,b,q)

Assertions:
- simtrir(b,o,q,o,b,q)

### D065 `dd:r53`

Dependencies: D064, D024

Assumptions:
- simtrir(b,o,q,o,b,q)
- sameclock(o,b,q,b,q,o)

Assertions:
- eqangle(b,o,o,q,b,q,b,o)

### D066 `ar:ratio chasing:squared_distance`

Dependencies: D002, D005

Assumptions:
- cong(b,q,d,q): (1/1)*|b-q|^2 + (-1/1)*|d-q|^2 = 0
- cong(b,q,o,q): (1/1)*|b-q|^2 + (-1/1)*|o-q|^2 = 0

Assertions:
- eqratio(d,q,o,q,o,q,d,q): (2/1)*|d-q|^2 + (-2/1)*|o-q|^2 = 0

### D067 `dd:r63`

Dependencies: D066, D028, D029

Assumptions:
- eqratio(d,q,o,q,o,q,d,q)
- eqangle(d,q,o,q,d,q,o,q)
- sameclock(d,q,o,o,d,q)

Assertions:
- simtrir(d,o,q,o,d,q)

### D068 `dd:r53`

Dependencies: D067, D027

Assumptions:
- simtrir(d,o,q,o,d,q)
- sameclock(o,d,q,d,q,o)

Assertions:
- eqangle(d,o,o,q,d,q,d,o)

### D069 `dd:r56`

Dependencies: D006

Assumptions:
- midp(o,a,b)

Assertions:
- coll(a,b,o)

### D070 `dd:r55`

Dependencies: D006

Assumptions:
- midp(o,a,b)

Assertions:
- cong(a,o,b,o)

### D071 `ar:angle chasing:directed_angle`

Dependencies: D043, D049, D052, D056, D062

Assumptions:
- eqangle(a,c,c,p,a,p,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-p) + (1/1)*∠(c-p) = 0
- eqangle(c,d,d,o,c,o,c,d): (-2/1)*∠(c-d) + (1/1)*∠(c-o) + (1/1)*∠(d-o) = 0
- eqangle(a,c,c,o,a,o,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-o) + (1/1)*∠(c-o) = 0
- eqangle(a,p,o,p,o,p,c,p): (-1/1)*∠(a-p) + (-1/1)*∠(c-p) + (2/1)*∠(o-p) = 0
- eqangle(a,d,d,o,a,o,a,d): (-2/1)*∠(a-d) + (1/1)*∠(a-o) + (1/1)*∠(d-o) = 0

Assertions:
- eqangle(a,d,c,d,a,o,o,p): (-1/1)*∠(a-d) + (1/1)*∠(a-o) + (1/1)*∠(c-d) + (-1/1)*∠(o-p) = 0

### D072 `internal_theorem`

Dependencies: D071

Assumptions:
- eqangle(a,d,c,d,a,o,o,p)

Assertions:
- equation_class Yuclid::SinOrDist(a,d,c,a,o,p)

### D073 `ar:angle chasing:directed_angle`

Dependencies: D059

Assumptions:
- eqangle(c,o,o,p,a,o,a,p): (1/1)*∠(a-o) + (-1/1)*∠(a-p) + (-1/1)*∠(c-o) + (1/1)*∠(o-p) = 0

Assertions:
- eqangle(a,o,c,o,a,p,o,p): (-1/1)*∠(a-o) + (1/1)*∠(a-p) + (1/1)*∠(c-o) + (-1/1)*∠(o-p) = 0

### D074 `internal_theorem`

Dependencies: D073

Assumptions:
- eqangle(a,o,c,o,a,p,o,p)

Assertions:
- equation_class Yuclid::SinOrDist(a,o,c,a,p,o)

### D075 `internal_theorem`

Dependencies: D034

Assumptions:
- ncoll(a,c,d)

Assertions:
- equation_class Yuclid::SinOrDist(a,c,d,c,a,d,a,d,c,d)

### D076 `internal_theorem`

Dependencies: D034

Assumptions:
- ncoll(a,c,d)

Assertions:
- equation_class Yuclid::SinOrDist(a,c,d,a,d,c,a,c,a,d)

### D077 `internal_theorem`

Dependencies: D033

Assumptions:
- ncoll(b,c,d)

Assertions:
- equation_class Yuclid::SinOrDist(b,c,d,c,b,d,b,d,c,d)

### D078 `internal_theorem`

Dependencies: D033

Assumptions:
- ncoll(b,c,d)

Assertions:
- equation_class Yuclid::SinOrDist(b,c,d,b,d,c,b,c,b,d)

### D079 `internal_theorem`

Dependencies: D035

Assumptions:
- ncoll(a,c,o)

Assertions:
- equation_class Yuclid::SinOrDist(a,c,o,a,o,c,a,c,a,o)

### D080 `internal_theorem`

Dependencies: D036

Assumptions:
- ncoll(a,d,o)

Assertions:
- equation_class Yuclid::SinOrDist(a,d,o,a,o,d,a,d,a,o)

### D081 `internal_theorem`

Dependencies: D037

Assumptions:
- ncoll(a,o,p)

Assertions:
- equation_class Yuclid::SinOrDist(a,o,p,a,p,o,a,o,a,p)

### D082 `internal_theorem`

Dependencies: D038

Assumptions:
- ncoll(a,b,q)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,q,b,a,q,a,q,b,q)

### D083 `internal_theorem`

Dependencies: D039

Assumptions:
- ncoll(a,d,q)

Assertions:
- equation_class Yuclid::SinOrDist(a,d,q,d,a,q,a,q,d,q)

### D084 `internal_theorem`

Dependencies: D040

Assumptions:
- ncoll(a,o,q)

Assertions:
- equation_class Yuclid::SinOrDist(a,o,q,o,a,q,a,q,o,q)

### D085 `internal_theorem`

Dependencies: D040

Assumptions:
- ncoll(a,o,q)

Assertions:
- equation_class Yuclid::SinOrDist(a,o,q,a,q,o,a,o,a,q)

### D086 `ar:length chasing:other`

Dependencies: D003, D070

Assumptions:
- cong(a,o,c,o): (1/1)*|a-o| + (-1/1)*|c-o| = 0
- cong(a,o,b,o): (1/1)*|a-o| + (-1/1)*|b-o| = 0

Assertions:
- cong(b,o,c,o): (1/1)*|b-o| + (-1/1)*|c-o| = 0

### D087 `ar:length chasing:other`

Dependencies: D004, D070

Assumptions:
- cong(a,o,d,o): (1/1)*|a-o| + (-1/1)*|d-o| = 0
- cong(a,o,b,o): (1/1)*|a-o| + (-1/1)*|b-o| = 0

Assertions:
- cong(b,o,d,o): (1/1)*|b-o| + (-1/1)*|d-o| = 0

### D088 `dd:r13`

Dependencies: D086

Assumptions:
- cong(b,o,c,o)

Assertions:
- eqangle(b,c,c,o,b,o,b,c)

### D089 `dd:r13`

Dependencies: D087

Assumptions:
- cong(b,o,d,o)

Assertions:
- eqangle(b,d,d,o,b,o,b,d)

### D090 `dd:r82`

Dependencies: D069, D030, D031, D032

Assumptions:
- coll(a,b,o)
- diff(a,o)
- diff(a,b)
- diff(b,o)

Assertions:
- para(a,o,b,o)

### D091 `dd:r82`

Dependencies: D069, D030, D031, D032

Assumptions:
- coll(a,b,o)
- diff(a,o)
- diff(a,b)
- diff(b,o)

Assertions:
- para(a,b,a,o)

### D092 `ar:angle chasing:directed_angle`

Dependencies: D043, D046, D052, D056, D059, D062, D065, D068, D088, D089, D090

Assumptions:
- eqangle(a,c,c,p,a,p,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-p) + (1/1)*∠(c-p) = 0
- eqangle(b,d,d,q,b,q,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-q) + (1/1)*∠(d-q) = 0
- eqangle(a,c,c,o,a,o,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-o) + (1/1)*∠(c-o) = 0
- eqangle(a,p,o,p,o,p,c,p): (-1/1)*∠(a-p) + (-1/1)*∠(c-p) + (2/1)*∠(o-p) = 0
- eqangle(c,o,o,p,a,o,a,p): (1/1)*∠(a-o) + (-1/1)*∠(a-p) + (-1/1)*∠(c-o) + (1/1)*∠(o-p) = 0
- eqangle(a,d,d,o,a,o,a,d): (-2/1)*∠(a-d) + (1/1)*∠(a-o) + (1/1)*∠(d-o) = 0
- eqangle(b,o,o,q,b,q,b,o): (-2/1)*∠(b-o) + (1/1)*∠(b-q) + (1/1)*∠(o-q) = 0
- eqangle(d,o,o,q,d,q,d,o): (-2/1)*∠(d-o) + (1/1)*∠(d-q) + (1/1)*∠(o-q) = 0
- eqangle(b,c,c,o,b,o,b,c): (-2/1)*∠(b-c) + (1/1)*∠(b-o) + (1/1)*∠(c-o) = 0
- eqangle(b,d,d,o,b,o,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-o) + (1/1)*∠(d-o) = 0
- para(a,o,b,o): (1/1)*∠(a-o) + (-1/1)*∠(b-o) = 0

Assertions:
- eqangle(b,c,b,q,a,d,a,p): (1/1)*∠(a-d) + (-1/1)*∠(a-p) + (-1/1)*∠(b-c) + (1/1)*∠(b-q) = 0

### D093 `ar:angle chasing:directed_angle`

Dependencies: D052, D062, D088, D089

Assumptions:
- eqangle(a,c,c,o,a,o,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-o) + (1/1)*∠(c-o) = 0
- eqangle(a,d,d,o,a,o,a,d): (-2/1)*∠(a-d) + (1/1)*∠(a-o) + (1/1)*∠(d-o) = 0
- eqangle(b,c,c,o,b,o,b,c): (-2/1)*∠(b-c) + (1/1)*∠(b-o) + (1/1)*∠(c-o) = 0
- eqangle(b,d,d,o,b,o,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-o) + (1/1)*∠(d-o) = 0

Assertions:
- eqangle(a,c,a,d,b,c,b,d): (-1/1)*∠(a-c) + (1/1)*∠(a-d) + (1/1)*∠(b-c) + (-1/1)*∠(b-d) = 0

### D094 `internal_theorem`

Dependencies: D093

Assumptions:
- eqangle(a,c,a,d,b,c,b,d)

Assertions:
- equation_class Yuclid::SinOrDist(c,a,d,c,b,d)

### D095 `ar:angle chasing:directed_angle`

Dependencies: D046, D062, D065, D068, D089, D090

Assumptions:
- eqangle(b,d,d,q,b,q,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-q) + (1/1)*∠(d-q) = 0
- eqangle(a,d,d,o,a,o,a,d): (-2/1)*∠(a-d) + (1/1)*∠(a-o) + (1/1)*∠(d-o) = 0
- eqangle(b,o,o,q,b,q,b,o): (-2/1)*∠(b-o) + (1/1)*∠(b-q) + (1/1)*∠(o-q) = 0
- eqangle(d,o,o,q,d,q,d,o): (-2/1)*∠(d-o) + (1/1)*∠(d-q) + (1/1)*∠(o-q) = 0
- eqangle(b,d,d,o,b,o,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-o) + (1/1)*∠(d-o) = 0
- para(a,o,b,o): (1/1)*∠(a-o) + (-1/1)*∠(b-o) = 0

Assertions:
- eqangle(a,q,o,q,a,q,a,d): (-1/1)*∠(a-d) + (1/1)*∠(o-q) = 0

### D096 `internal_theorem`

Dependencies: D095

Assumptions:
- eqangle(a,q,o,q,a,q,a,d)

Assertions:
- equation_class Yuclid::SinOrDist(a,q,o,d,a,q)

### D097 `ar:angle chasing:directed_angle`

Dependencies: D091

Assumptions:
- para(a,b,a,o): (1/1)*∠(a-b) + (-1/1)*∠(a-o) = 0

Assertions:
- eqangle(a,b,a,q,a,o,a,q): (-1/1)*∠(a-b) + (1/1)*∠(a-o) = 0

### D098 `internal_theorem`

Dependencies: D097

Assumptions:
- eqangle(a,b,a,q,a,o,a,q)

Assertions:
- equation_class Yuclid::SinOrDist(b,a,q,o,a,q)

### D099 `ar:angle chasing:directed_angle`

Dependencies: D049, D052, D089, D090

Assumptions:
- eqangle(c,d,d,o,c,o,c,d): (-2/1)*∠(c-d) + (1/1)*∠(c-o) + (1/1)*∠(d-o) = 0
- eqangle(a,c,c,o,a,o,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-o) + (1/1)*∠(c-o) = 0
- eqangle(b,d,d,o,b,o,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-o) + (1/1)*∠(d-o) = 0
- para(a,o,b,o): (1/1)*∠(a-o) + (-1/1)*∠(b-o) = 0

Assertions:
- eqangle(a,c,c,o,b,d,c,d): (-1/1)*∠(a-c) + (1/1)*∠(b-d) + (-1/1)*∠(c-d) + (1/1)*∠(c-o) = 0

### D100 `internal_theorem`

Dependencies: D099

Assumptions:
- eqangle(a,c,c,o,b,d,c,d)

Assertions:
- equation_class Yuclid::SinOrDist(a,c,o,b,d,c)

### D101 `ar:angle chasing:directed_angle`

Dependencies: D046, D062, D065, D068, D089, D090

Assumptions:
- eqangle(b,d,d,q,b,q,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-q) + (1/1)*∠(d-q) = 0
- eqangle(a,d,d,o,a,o,a,d): (-2/1)*∠(a-d) + (1/1)*∠(a-o) + (1/1)*∠(d-o) = 0
- eqangle(b,o,o,q,b,q,b,o): (-2/1)*∠(b-o) + (1/1)*∠(b-q) + (1/1)*∠(o-q) = 0
- eqangle(d,o,o,q,d,q,d,o): (-2/1)*∠(d-o) + (1/1)*∠(d-q) + (1/1)*∠(o-q) = 0
- eqangle(b,d,d,o,b,o,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-o) + (1/1)*∠(d-o) = 0
- para(a,o,b,o): (1/1)*∠(a-o) + (-1/1)*∠(b-o) = 0

Assertions:
- eqangle(a,d,d,q,a,o,d,o): (-1/1)*∠(a-d) + (1/1)*∠(a-o) + (-1/1)*∠(d-o) + (1/1)*∠(d-q) = 0

### D102 `internal_theorem`

Dependencies: D101

Assumptions:
- eqangle(a,d,d,q,a,o,d,o)

Assertions:
- equation_class Yuclid::SinOrDist(a,d,q,a,o,d)

### D103 `ar:angle chasing:directed_angle`

Dependencies: D046, D062, D065, D068, D089, D090, D091

Assumptions:
- eqangle(b,d,d,q,b,q,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-q) + (1/1)*∠(d-q) = 0
- eqangle(a,d,d,o,a,o,a,d): (-2/1)*∠(a-d) + (1/1)*∠(a-o) + (1/1)*∠(d-o) = 0
- eqangle(b,o,o,q,b,q,b,o): (-2/1)*∠(b-o) + (1/1)*∠(b-q) + (1/1)*∠(o-q) = 0
- eqangle(d,o,o,q,d,q,d,o): (-2/1)*∠(d-o) + (1/1)*∠(d-q) + (1/1)*∠(o-q) = 0
- eqangle(b,d,d,o,b,o,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-o) + (1/1)*∠(d-o) = 0
- para(a,o,b,o): (1/1)*∠(a-o) + (-1/1)*∠(b-o) = 0
- para(a,b,a,o): (1/1)*∠(a-b) + (-1/1)*∠(a-o) = 0

Assertions:
- eqangle(a,b,b,q,d,o,a,d): (-1/1)*∠(a-b) + (-1/1)*∠(a-d) + (1/1)*∠(b-q) + (1/1)*∠(d-o) = 0

### D104 `internal_theorem`

Dependencies: D103

Assumptions:
- eqangle(a,b,b,q,d,o,a,d)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,q,a,d,o)

### D105 `ar:ratio chasing:sine_squared+squared_distance` [SINE-DISTANCE BRIDGE]

Dependencies: D002, D005, D072, D074, D075, D076, D077, D078, D079, D080, D081, D082, D083, D084, D085, D094, D096, D098, D100, D102, D104

Assumptions:
- cong(b,q,d,q): (1/1)*|b-q|^2 + (-1/1)*|d-q|^2 = 0
- cong(b,q,o,q): (1/1)*|b-q|^2 + (-1/1)*|o-q|^2 = 0
- equation_class Yuclid::SinOrDist(a,d,c,a,o,p): (1/1)*\sin² ∠(a d c) + (-1/1)*\sin² ∠(a o p) = 0
- equation_class Yuclid::SinOrDist(a,o,c,a,p,o): (1/1)*\sin² ∠(a o c) + (-1/1)*\sin² ∠(a p o) = 0
- equation_class Yuclid::SinOrDist(a,c,d,c,a,d,a,d,c,d): (1/1)*\sin² ∠(a c d) + (-1/1)*\sin² ∠(c a d) + (-1/1)*|a-d|^2 + (1/1)*|c-d|^2 = 0
- equation_class Yuclid::SinOrDist(a,c,d,a,d,c,a,c,a,d): (1/1)*\sin² ∠(a c d) + (-1/1)*\sin² ∠(a d c) + (1/1)*|a-c|^2 + (-1/1)*|a-d|^2 = 0
- equation_class Yuclid::SinOrDist(b,c,d,c,b,d,b,d,c,d): (1/1)*\sin² ∠(b c d) + (-1/1)*\sin² ∠(c b d) + (-1/1)*|b-d|^2 + (1/1)*|c-d|^2 = 0
- equation_class Yuclid::SinOrDist(b,c,d,b,d,c,b,c,b,d): (1/1)*\sin² ∠(b c d) + (-1/1)*\sin² ∠(b d c) + (1/1)*|b-c|^2 + (-1/1)*|b-d|^2 = 0
- equation_class Yuclid::SinOrDist(a,c,o,a,o,c,a,c,a,o): (1/1)*\sin² ∠(a c o) + (-1/1)*\sin² ∠(a o c) + (1/1)*|a-c|^2 + (-1/1)*|a-o|^2 = 0
- equation_class Yuclid::SinOrDist(a,d,o,a,o,d,a,d,a,o): (1/1)*\sin² ∠(a d o) + (-1/1)*\sin² ∠(a o d) + (1/1)*|a-d|^2 + (-1/1)*|a-o|^2 = 0
- equation_class Yuclid::SinOrDist(a,o,p,a,p,o,a,o,a,p): (1/1)*\sin² ∠(a o p) + (-1/1)*\sin² ∠(a p o) + (1/1)*|a-o|^2 + (-1/1)*|a-p|^2 = 0
- equation_class Yuclid::SinOrDist(a,b,q,b,a,q,a,q,b,q): (1/1)*\sin² ∠(a b q) + (-1/1)*\sin² ∠(b a q) + (-1/1)*|a-q|^2 + (1/1)*|b-q|^2 = 0
- equation_class Yuclid::SinOrDist(a,d,q,d,a,q,a,q,d,q): (1/1)*\sin² ∠(a d q) + (-1/1)*\sin² ∠(d a q) + (-1/1)*|a-q|^2 + (1/1)*|d-q|^2 = 0
- equation_class Yuclid::SinOrDist(a,o,q,o,a,q,a,q,o,q): (1/1)*\sin² ∠(a o q) + (-1/1)*\sin² ∠(o a q) + (-1/1)*|a-q|^2 + (1/1)*|o-q|^2 = 0
- equation_class Yuclid::SinOrDist(a,o,q,a,q,o,a,o,a,q): (1/1)*\sin² ∠(a o q) + (-1/1)*\sin² ∠(a q o) + (1/1)*|a-o|^2 + (-1/1)*|a-q|^2 = 0
- equation_class Yuclid::SinOrDist(c,a,d,c,b,d): (1/1)*\sin² ∠(c a d) + (-1/1)*\sin² ∠(c b d) = 0
- equation_class Yuclid::SinOrDist(a,q,o,d,a,q): (1/1)*\sin² ∠(a q o) + (-1/1)*\sin² ∠(d a q) = 0
- equation_class Yuclid::SinOrDist(b,a,q,o,a,q): (1/1)*\sin² ∠(b a q) + (-1/1)*\sin² ∠(o a q) = 0
- equation_class Yuclid::SinOrDist(a,c,o,b,d,c): (1/1)*\sin² ∠(a c o) + (-1/1)*\sin² ∠(b d c) = 0
- equation_class Yuclid::SinOrDist(a,d,q,a,o,d): (1/1)*\sin² ∠(a d q) + (-1/1)*\sin² ∠(a o d) = 0
- equation_class Yuclid::SinOrDist(a,b,q,a,d,o): (1/1)*\sin² ∠(a b q) + (-1/1)*\sin² ∠(a d o) = 0

Assertions:
- eqratio(a,d,a,p,b,c,b,q): (1/1)*|a-d|^2 + (-1/1)*|a-p|^2 + (-1/1)*|b-c|^2 + (1/1)*|b-q|^2 = 0

### D106 `dd:r62`

Dependencies: D105, D092, D008

Assumptions:
- eqratio(a,d,a,p,b,c,b,q)
- eqangle(b,c,b,q,a,d,a,p)
- sameclock(q,b,c,p,a,d)

Assertions:
- simtri(a,d,p,b,c,q)

### D107 `dd:r52`

Dependencies: D106, D007

Assumptions:
- simtri(a,d,p,b,c,q)
- sameclock(c,q,b,d,p,a)

Assertions:
- eqratio(a,p,b,q,d,p,c,q)

### D108 `ar:ratio chasing:squared_distance`

Dependencies: D000, D002, D107

Assumptions:
- cong(a,p,c,p): (1/1)*|a-p|^2 + (-1/1)*|c-p|^2 = 0
- cong(b,q,d,q): (1/1)*|b-q|^2 + (-1/1)*|d-q|^2 = 0
- eqratio(a,p,b,q,d,p,c,q): (1/1)*|a-p|^2 + (-1/1)*|b-q|^2 + (1/1)*|c-q|^2 + (-1/1)*|d-p|^2 = 0

Assertions:
- eqratio(c,p,d,p,d,q,c,q): (1/1)*|c-p|^2 + (1/1)*|c-q|^2 + (-1/1)*|d-p|^2 + (-1/1)*|d-q|^2 = 0
