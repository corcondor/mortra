# 2011AsiaPacificMOp3: Yuclid proof trace

- Certificate: `data/hageo-409-current-native-certified-rerun-2026-08-24-runs/proofs/2011AsiaPacificMOp3.json`
- Deductions read: 199
- Order: Yuclid certificate order; every deduction is retained.

## Complete deduction trace

### D000 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(a,b,c1)

### D001 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(a,b,c2)

### D002 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(a,c,b1)

### D003 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(a,c,b2)

### D004 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,o,b,o)

### D005 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(b,c,b,o)

### D006 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(p,m1,b1,m1)

### D007 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(b,c,c,o)

### D008 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(p,m2,c1,m2)

### D009 `construction`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(b,c,b,b1,b,b1,a,b)

### D010 `construction`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(b,c,c,c1,c,c1,a,c)

### D011 `construction`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(b,c,c,o,b,o,b,c)

### D012 `construction`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(b,o,c,o,c,o,b,c)

### D013 `construction`

Dependencies: none

Assumptions: none

Assertions:
- midp(m1,b1,b2)

### D014 `construction`

Dependencies: none

Assumptions: none

Assertions:
- midp(m2,c1,c2)

### D015 `construction`

Dependencies: none

Assumptions: none

Assertions:
- perp(b,b1,b,b2)

### D016 `construction`

Dependencies: none

Assumptions: none

Assertions:
- perp(c,c1,c,c2)

### D017 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(p,c1,m2,c1,m2,p)

### D018 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(p,m2,c1,m2,p,m2,c1,m2)

### D019 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(c1,m2,p,p,c1,m2)

### D020 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(p,a,m2,b,m2,p)

### D021 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(a,m2,p,p,b,m2)

### D022 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(p,b1,m1,b1,m1,p)

### D023 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(p,m1,b1,m1,p,m1,b1,m1)

### D024 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(b1,m1,p,p,b1,m1)

### D025 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(a,p,m1,p,m1,c)

### D026 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(p,m1,a,c,p,m1)

### D027 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,o,b,o,a,o,b,o)

### D028 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(a,o,b,b,a,o)

### D029 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(a,c,o,c,o,a)

### D030 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,o,c,o,a,o,c,o)

### D031 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(c,o,a,a,c,o)

### D032 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,c1)

### D033 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,b)

### D034 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,c1)

### D035 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,b1)

### D036 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,c)

### D037 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(c,b1)

### D038 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,m1)

### D039 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(c,m1)

### D040 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b1,m1)

### D041 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,b2)

### D042 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(c,b2)

### D043 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b1,b2)

### D044 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(m1,b2)

### D045 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,c2)

### D046 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,c2)

### D047 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(c1,c2)

### D048 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,m2)

### D049 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(c2,m2)

### D050 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,m2)

### D051 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(c1,m2)

### D052 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(p,b1,b2)

### D053 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(c,c1,c2)

### D054 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(p,c2)

### D055 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(p,c1)

### D056 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(p,b1)

### D057 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(p,b2)

### D058 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,b2)

### D059 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,b1)

### D060 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(c,c1)

### D061 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(c,c2)

### D062 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,b,c)

### D063 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(b,c,m1)

### D064 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,b1,c2)

### D065 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,c,m2)

### D066 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(b,c,m2)

### D067 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,b1,m2)

### D068 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,m1,m2)

### D069 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(b,m1,m2)

### D070 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,b2,m2)

### D071 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(m1,b2,m2)

### D072 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(b1,c2,m2)

### D073 `ar:ratio chasing:squared_distance`

Dependencies: D008

Assumptions:
- cong(p,m2,c1,m2): (1/1)*|p-m2|^2 + (-1/1)*|c1-m2|^2 = 0

Assertions:
- eqratio(p,m2,c1,m2,c1,m2,p,m2): (2/1)*|p-m2|^2 + (-2/1)*|c1-m2|^2 = 0

### D074 `dd:r63`

Dependencies: D073, D018, D019

Assumptions:
- eqratio(p,m2,c1,m2,c1,m2,p,m2)
- eqangle(p,m2,c1,m2,p,m2,c1,m2)
- sameclock(c1,m2,p,p,c1,m2)

Assertions:
- simtrir(p,c1,m2,c1,p,m2)

### D075 `dd:r53`

Dependencies: D074, D017

Assumptions:
- simtrir(p,c1,m2,c1,p,m2)
- sameclock(p,c1,m2,c1,m2,p)

Assertions:
- eqangle(p,c1,c1,m2,p,m2,p,c1)

### D076 `ar:ratio chasing:squared_distance`

Dependencies: D006

Assumptions:
- cong(p,m1,b1,m1): (1/1)*|p-m1|^2 + (-1/1)*|b1-m1|^2 = 0

Assertions:
- eqratio(p,m1,b1,m1,b1,m1,p,m1): (2/1)*|p-m1|^2 + (-2/1)*|b1-m1|^2 = 0

### D077 `dd:r63`

Dependencies: D076, D023, D024

Assumptions:
- eqratio(p,m1,b1,m1,b1,m1,p,m1)
- eqangle(p,m1,b1,m1,p,m1,b1,m1)
- sameclock(b1,m1,p,p,b1,m1)

Assertions:
- simtrir(p,b1,m1,b1,p,m1)

### D078 `dd:r53`

Dependencies: D077, D022

Assumptions:
- simtrir(p,b1,m1,b1,p,m1)
- sameclock(p,b1,m1,b1,m1,p)

Assertions:
- eqangle(p,b1,b1,m1,p,m1,p,b1)

### D079 `ar:ratio chasing:squared_distance`

Dependencies: D004

Assumptions:
- cong(a,o,b,o): (1/1)*|a-o|^2 + (-1/1)*|b-o|^2 = 0

Assertions:
- eqratio(a,o,b,o,b,o,a,o): (2/1)*|a-o|^2 + (-2/1)*|b-o|^2 = 0

### D080 `dd:r63`

Dependencies: D079, D027, D028

Assumptions:
- eqratio(a,o,b,o,b,o,a,o)
- eqangle(a,o,b,o,a,o,b,o)
- sameclock(a,o,b,b,a,o)

Assertions:
- simtrir(a,b,o,b,a,o)

### D081 `dd:r53`

Dependencies: D080, D028

Assumptions:
- simtrir(a,b,o,b,a,o)
- sameclock(a,o,b,b,a,o)

Assertions:
- eqangle(a,b,b,o,a,o,a,b)

### D082 `ar:ratio chasing:squared_distance`

Dependencies: D004, D005, D007

Assumptions:
- cong(a,o,b,o): (1/1)*|a-o|^2 + (-1/1)*|b-o|^2 = 0
- cong(b,c,b,o): (1/1)*|b-c|^2 + (-1/1)*|b-o|^2 = 0
- cong(b,c,c,o): (1/1)*|b-c|^2 + (-1/1)*|c-o|^2 = 0

Assertions:
- eqratio(a,o,c,o,c,o,a,o): (2/1)*|a-o|^2 + (-2/1)*|c-o|^2 = 0

### D083 `dd:r63`

Dependencies: D082, D030, D031

Assumptions:
- eqratio(a,o,c,o,c,o,a,o)
- eqangle(a,o,c,o,a,o,c,o)
- sameclock(c,o,a,a,c,o)

Assertions:
- simtrir(a,c,o,c,a,o)

### D084 `dd:r53`

Dependencies: D083, D029

Assumptions:
- simtrir(a,c,o,c,a,o)
- sameclock(a,c,o,c,o,a)

Assertions:
- eqangle(a,c,c,o,a,o,a,c)

### D085 `dd:r82`

Dependencies: D000, D032, D033, D034

Assumptions:
- coll(a,b,c1)
- diff(a,c1)
- diff(a,b)
- diff(b,c1)

Assertions:
- para(a,c1,b,c1)

### D086 `dd:r82`

Dependencies: D000, D032, D033, D034

Assumptions:
- coll(a,b,c1)
- diff(a,c1)
- diff(a,b)
- diff(b,c1)

Assertions:
- para(a,b,a,c1)

### D087 `dd:r82`

Dependencies: D002, D035, D036, D037

Assumptions:
- coll(a,c,b1)
- diff(a,b1)
- diff(a,c)
- diff(c,b1)

Assertions:
- para(a,b1,c,b1)

### D088 `dd:r82`

Dependencies: D002, D035, D036, D037

Assumptions:
- coll(a,c,b1)
- diff(a,b1)
- diff(a,c)
- diff(c,b1)

Assertions:
- para(a,c,a,b1)

### D089 `dd:r82`

Dependencies: D003, D036, D041, D042

Assumptions:
- coll(a,c,b2)
- diff(a,c)
- diff(a,b2)
- diff(c,b2)

Assertions:
- para(a,c,c,b2)

### D090 `dd:r82`

Dependencies: D003, D036, D041, D042

Assumptions:
- coll(a,c,b2)
- diff(a,c)
- diff(a,b2)
- diff(c,b2)

Assertions:
- para(a,c,a,b2)

### D091 `ar:angle chasing:directed_angle`

Dependencies: D087, D088, D089

Assumptions:
- para(a,b1,c,b1): (1/1)*∠(a-b1) + (-1/1)*∠(c-b1) = 0
- para(a,c,a,b1): (1/1)*∠(a-c) + (-1/1)*∠(a-b1) = 0
- para(a,c,c,b2): (1/1)*∠(a-c) + (-1/1)*∠(c-b2) = 0

Assertions:
- para(c,b1,c,b2): (1/1)*∠(c-b1) + (-1/1)*∠(c-b2) = 0

### D092 `dd:r28`

Dependencies: D091

Assumptions:
- para(c,b1,c,b2)

Assertions:
- coll(c,b1,b2)

### D093 `dd:r82`

Dependencies: D092, D037, D043, D042

Assumptions:
- coll(c,b1,b2)
- diff(c,b1)
- diff(b1,b2)
- diff(c,b2)

Assertions:
- para(c,b1,b1,b2)

### D094 `dd:r56`

Dependencies: D013

Assumptions:
- midp(m1,b1,b2)

Assertions:
- coll(b1,m1,b2)

### D095 `dd:r55`

Dependencies: D013

Assumptions:
- midp(m1,b1,b2)

Assertions:
- cong(b1,m1,m1,b2)

### D096 `dd:r82`

Dependencies: D001, D033, D045, D046

Assumptions:
- coll(a,b,c2)
- diff(a,b)
- diff(b,c2)
- diff(a,c2)

Assertions:
- para(a,b,a,c2)

### D097 `dd:r82`

Dependencies: D001, D033, D045, D046

Assumptions:
- coll(a,b,c2)
- diff(a,b)
- diff(b,c2)
- diff(a,c2)

Assertions:
- para(a,b,b,c2)

### D098 `ar:angle chasing:directed_angle`

Dependencies: D086, D096

Assumptions:
- para(a,b,a,c1): (1/1)*∠(a-b) + (-1/1)*∠(a-c1) = 0
- para(a,b,a,c2): (1/1)*∠(a-b) + (-1/1)*∠(a-c2) = 0

Assertions:
- para(a,c1,a,c2): (1/1)*∠(a-c1) + (-1/1)*∠(a-c2) = 0

### D099 `dd:r28`

Dependencies: D098

Assumptions:
- para(a,c1,a,c2)

Assertions:
- coll(a,c1,c2)

### D100 `dd:r82`

Dependencies: D099, D032, D047, D046

Assumptions:
- coll(a,c1,c2)
- diff(a,c1)
- diff(c1,c2)
- diff(a,c2)

Assertions:
- para(a,c1,c1,c2)

### D101 `dd:r56`

Dependencies: D014

Assumptions:
- midp(m2,c1,c2)

Assertions:
- coll(c1,c2,m2)

### D102 `dd:r55`

Dependencies: D014

Assumptions:
- midp(m2,c1,c2)

Assertions:
- cong(c1,m2,c2,m2)

### D103 `ar:angle chasing:directed_angle`

Dependencies: D096, D097

Assumptions:
- para(a,b,a,c2): (1/1)*∠(a-b) + (-1/1)*∠(a-c2) = 0
- para(a,b,b,c2): (1/1)*∠(a-b) + (-1/1)*∠(b-c2) = 0

Assertions:
- eqangle(a,c2,b1,c2,b,c2,b1,c2): (-1/1)*∠(a-c2) + (1/1)*∠(b-c2) = 0

### D104 `internal_theorem`

Dependencies: D103

Assumptions:
- eqangle(a,c2,b1,c2,b,c2,b1,c2)

Assertions:
- equation_class Yuclid::SinOrDist(a,c2,b1,b,c2,b1)

### D105 `ar:angle chasing:directed_angle`

Dependencies: D088, D090

Assumptions:
- para(a,c,a,b1): (1/1)*∠(a-c) + (-1/1)*∠(a-b1) = 0
- para(a,c,a,b2): (1/1)*∠(a-c) + (-1/1)*∠(a-b2) = 0

Assertions:
- eqangle(a,b1,a,c2,a,b2,a,c2): (-1/1)*∠(a-b1) + (1/1)*∠(a-b2) = 0

### D106 `internal_theorem`

Dependencies: D105

Assumptions:
- eqangle(a,b1,a,c2,a,b2,a,c2)

Assertions:
- equation_class Yuclid::SinOrDist(b1,a,c2,b2,a,c2)

### D107 `ar:angle chasing:directed_angle`

Dependencies: D090, D096

Assumptions:
- para(a,c,a,b2): (1/1)*∠(a-c) + (-1/1)*∠(a-b2) = 0
- para(a,b,a,c2): (1/1)*∠(a-b) + (-1/1)*∠(a-c2) = 0

Assertions:
- eqangle(a,b,a,c,a,c2,a,b2): (-1/1)*∠(a-b) + (1/1)*∠(a-c) + (-1/1)*∠(a-b2) + (1/1)*∠(a-c2) = 0

### D108 `internal_theorem`

Dependencies: D107

Assumptions:
- eqangle(a,b,a,c,a,c2,a,b2)

Assertions:
- equation_class Yuclid::SinOrDist(b,a,c,b2,a,c2)

### D109 `ar:angle chasing:directed_angle`

Dependencies: D088

Assumptions:
- para(a,c,a,b1): (1/1)*∠(a-c) + (-1/1)*∠(a-b1) = 0

Assertions:
- eqangle(a,c,a,m2,a,b1,a,m2): (-1/1)*∠(a-c) + (1/1)*∠(a-b1) = 0

### D110 `internal_theorem`

Dependencies: D109

Assumptions:
- eqangle(a,c,a,m2,a,b1,a,m2)

Assertions:
- equation_class Yuclid::SinOrDist(c,a,m2,b1,a,m2)

### D111 `ar:angle chasing:directed_angle`

Dependencies: D090

Assumptions:
- para(a,c,a,b2): (1/1)*∠(a-c) + (-1/1)*∠(a-b2) = 0

Assertions:
- eqangle(a,c,a,m2,a,b2,a,m2): (-1/1)*∠(a-c) + (1/1)*∠(a-b2) = 0

### D112 `internal_theorem`

Dependencies: D111

Assumptions:
- eqangle(a,c,a,m2,a,b2,a,m2)

Assertions:
- equation_class Yuclid::SinOrDist(c,a,m2,b2,a,m2)

### D113 `internal_theorem`

Dependencies: D058, D059, D015

Assumptions:
- diff(b,b2)
- diff(b,b1)
- perp(b,b1,b,b2)

Assertions:
- equation_class Yuclid::SquaredDist(b,b1,b,b2,b1,b2)

### D114 `internal_theorem`

Dependencies: D060, D061, D016

Assumptions:
- diff(c,c1)
- diff(c,c2)
- perp(c,c1,c,c2)

Assertions:
- equation_class Yuclid::SquaredDist(c,c1,c,c2,c1,c2)

### D115 `internal_theorem`

Dependencies: D062

Assumptions:
- ncoll(a,b,c)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,c,b,a,c,a,c,b,c)

### D116 `internal_theorem`

Dependencies: D063

Assumptions:
- ncoll(b,c,m1)

Assertions:
- equation_class Yuclid::SinOrDist(b,c,m1,c,b,m1,b,m1,c,m1)

### D117 `internal_theorem`

Dependencies: D064

Assumptions:
- ncoll(a,b1,c2)

Assertions:
- equation_class Yuclid::SinOrDist(a,b1,c2,b1,a,c2,a,c2,b1,c2)

### D118 `internal_theorem`

Dependencies: D064

Assumptions:
- ncoll(a,b1,c2)

Assertions:
- equation_class Yuclid::SinOrDist(a,b1,c2,a,c2,b1,a,b1,a,c2)

### D119 `internal_theorem`

Dependencies: D065

Assumptions:
- ncoll(a,c,m2)

Assertions:
- equation_class Yuclid::SinOrDist(a,c,m2,c,a,m2,a,m2,c,m2)

### D120 `internal_theorem`

Dependencies: D065

Assumptions:
- ncoll(a,c,m2)

Assertions:
- equation_class Yuclid::SinOrDist(a,c,m2,a,m2,c,a,c,a,m2)

### D121 `internal_theorem`

Dependencies: D066

Assumptions:
- ncoll(b,c,m2)

Assertions:
- equation_class Yuclid::SinOrDist(b,c,m2,b,m2,c,b,c,b,m2)

### D122 `internal_theorem`

Dependencies: D067

Assumptions:
- ncoll(a,b1,m2)

Assertions:
- equation_class Yuclid::SinOrDist(a,b1,m2,b1,a,m2,a,m2,b1,m2)

### D123 `internal_theorem`

Dependencies: D067

Assumptions:
- ncoll(a,b1,m2)

Assertions:
- equation_class Yuclid::SinOrDist(a,b1,m2,a,m2,b1,a,b1,a,m2)

### D124 `internal_theorem`

Dependencies: D068

Assumptions:
- ncoll(a,m1,m2)

Assertions:
- equation_class Yuclid::SinOrDist(a,m1,m2,a,m2,m1,a,m1,a,m2)

### D125 `internal_theorem`

Dependencies: D069

Assumptions:
- ncoll(b,m1,m2)

Assertions:
- equation_class Yuclid::SinOrDist(b,m1,m2,m1,b,m2,b,m2,m1,m2)

### D126 `internal_theorem`

Dependencies: D069

Assumptions:
- ncoll(b,m1,m2)

Assertions:
- equation_class Yuclid::SinOrDist(b,m1,m2,b,m2,m1,b,m1,b,m2)

### D127 `internal_theorem`

Dependencies: D070

Assumptions:
- ncoll(a,b2,m2)

Assertions:
- equation_class Yuclid::SinOrDist(a,b2,m2,b2,a,m2,a,m2,b2,m2)

### D128 `internal_theorem`

Dependencies: D071

Assumptions:
- ncoll(m1,b2,m2)

Assertions:
- equation_class Yuclid::SinOrDist(m1,b2,m2,b2,m1,m2,m1,m2,b2,m2)

### D129 `internal_theorem`

Dependencies: D072

Assumptions:
- ncoll(b1,c2,m2)

Assertions:
- equation_class Yuclid::SinOrDist(b1,c2,m2,b1,m2,c2,b1,c2,b1,m2)

### D130 `ar:length chasing:other`

Dependencies: D006, D095

Assumptions:
- cong(p,m1,b1,m1): (1/1)*|p-m1| + (-1/1)*|b1-m1| = 0
- cong(b1,m1,m1,b2): (1/1)*|b1-m1| + (-1/1)*|m1-b2| = 0

Assertions:
- cong(p,m1,m1,b2): (1/1)*|p-m1| + (-1/1)*|m1-b2| = 0

### D131 `dd:r13`

Dependencies: D130

Assumptions:
- cong(p,m1,m1,b2)

Assertions:
- eqangle(p,b2,m1,b2,p,m1,p,b2)

### D132 `ar:length chasing:other`

Dependencies: D008, D102

Assumptions:
- cong(p,m2,c1,m2): (1/1)*|p-m2| + (-1/1)*|c1-m2| = 0
- cong(c1,m2,c2,m2): (1/1)*|c1-m2| + (-1/1)*|c2-m2| = 0

Assertions:
- cong(p,m2,c2,m2): (1/1)*|p-m2| + (-1/1)*|c2-m2| = 0

### D133 `dd:r13`

Dependencies: D132

Assumptions:
- cong(p,m2,c2,m2)

Assertions:
- eqangle(p,c2,c2,m2,p,m2,p,c2)

### D134 `dd:r82`

Dependencies: D094, D040, D043, D044

Assumptions:
- coll(b1,m1,b2)
- diff(b1,m1)
- diff(b1,b2)
- diff(m1,b2)

Assertions:
- para(b1,m1,m1,b2)

### D135 `dd:r82`

Dependencies: D094, D040, D043, D044

Assumptions:
- coll(b1,m1,b2)
- diff(b1,m1)
- diff(b1,b2)
- diff(m1,b2)

Assertions:
- para(b1,m1,b1,b2)

### D136 `internal_theorem`

Dependencies: D095, D094

Assumptions:
- cong(b1,m1,m1,b2)
- coll(b1,m1,b2)

Assertions:
- equation_class Yuclid::SquaredDist(b,b1,b,m1,b,b2,b1,b2)

### D137 `internal_theorem`

Dependencies: D095, D094

Assumptions:
- cong(b1,m1,m1,b2)
- coll(b1,m1,b2)

Assertions:
- equation_class Yuclid::SquaredDist(p,b1,p,m1,p,b2,b1,b2)

### D138 `dd:r82`

Dependencies: D101, D051, D047, D049

Assumptions:
- coll(c1,c2,m2)
- diff(c1,m2)
- diff(c1,c2)
- diff(c2,m2)

Assertions:
- para(c1,m2,c2,m2)

### D139 `dd:r82`

Dependencies: D101, D051, D047, D049

Assumptions:
- coll(c1,c2,m2)
- diff(c1,m2)
- diff(c1,c2)
- diff(c2,m2)

Assertions:
- para(c1,c2,c1,m2)

### D140 `internal_theorem`

Dependencies: D102, D101

Assumptions:
- cong(c1,m2,c2,m2)
- coll(c1,c2,m2)

Assertions:
- equation_class Yuclid::SquaredDist(c,c1,c,c2,c,m2,c1,c2)

### D141 `internal_theorem`

Dependencies: D102, D101

Assumptions:
- cong(c1,m2,c2,m2)
- coll(c1,c2,m2)

Assertions:
- equation_class Yuclid::SquaredDist(p,c1,p,c2,p,m2,c1,c2)

### D142 `ar:angle chasing:directed_angle`

Dependencies: D100, D139

Assumptions:
- para(a,c1,c1,c2): (1/1)*∠(a-c1) + (-1/1)*∠(c1-c2) = 0
- para(c1,c2,c1,m2): (1/1)*∠(c1-c2) + (-1/1)*∠(c1-m2) = 0

Assertions:
- para(a,c1,c1,m2): (1/1)*∠(a-c1) + (-1/1)*∠(c1-m2) = 0

### D143 `dd:r28`

Dependencies: D142

Assumptions:
- para(a,c1,c1,m2)

Assertions:
- coll(a,c1,m2)

### D144 `dd:r82`

Dependencies: D143, D051, D048, D032

Assumptions:
- coll(a,c1,m2)
- diff(c1,m2)
- diff(a,m2)
- diff(a,c1)

Assertions:
- para(a,m2,c1,m2)

### D145 `ar:angle chasing:directed_angle`

Dependencies: D085, D100, D139

Assumptions:
- para(a,c1,b,c1): (1/1)*∠(a-c1) + (-1/1)*∠(b-c1) = 0
- para(a,c1,c1,c2): (1/1)*∠(a-c1) + (-1/1)*∠(c1-c2) = 0
- para(c1,c2,c1,m2): (1/1)*∠(c1-c2) + (-1/1)*∠(c1-m2) = 0

Assertions:
- para(b,c1,c1,m2): (1/1)*∠(b-c1) + (-1/1)*∠(c1-m2) = 0

### D146 `dd:r28`

Dependencies: D145

Assumptions:
- para(b,c1,c1,m2)

Assertions:
- coll(b,c1,m2)

### D147 `dd:r82`

Dependencies: D146, D034, D050, D051

Assumptions:
- coll(b,c1,m2)
- diff(b,c1)
- diff(b,m2)
- diff(c1,m2)

Assertions:
- para(b,c1,b,m2)

### D148 `ar:angle chasing:directed_angle`

Dependencies: D085, D100, D139, D144, D147

Assumptions:
- para(a,c1,b,c1): (1/1)*∠(a-c1) + (-1/1)*∠(b-c1) = 0
- para(a,c1,c1,c2): (1/1)*∠(a-c1) + (-1/1)*∠(c1-c2) = 0
- para(c1,c2,c1,m2): (1/1)*∠(c1-c2) + (-1/1)*∠(c1-m2) = 0
- para(a,m2,c1,m2): (1/1)*∠(a-m2) + (-1/1)*∠(c1-m2) = 0
- para(b,c1,b,m2): (1/1)*∠(b-c1) + (-1/1)*∠(b-m2) = 0

Assertions:
- eqangle(a,m2,p,m2,b,m2,p,m2): (-1/1)*∠(a-m2) + (1/1)*∠(b-m2) = 0

### D149 `ar:angle chasing:directed_angle`

Dependencies: D086, D097, D100, D138, D139

Assumptions:
- para(a,b,a,c1): (1/1)*∠(a-b) + (-1/1)*∠(a-c1) = 0
- para(a,b,b,c2): (1/1)*∠(a-b) + (-1/1)*∠(b-c2) = 0
- para(a,c1,c1,c2): (1/1)*∠(a-c1) + (-1/1)*∠(c1-c2) = 0
- para(c1,m2,c2,m2): (1/1)*∠(c1-m2) + (-1/1)*∠(c2-m2) = 0
- para(c1,c2,c1,m2): (1/1)*∠(c1-c2) + (-1/1)*∠(c1-m2) = 0

Assertions:
- eqangle(b,c2,b1,c2,c2,m2,b1,c2): (-1/1)*∠(b-c2) + (1/1)*∠(c2-m2) = 0

### D150 `internal_theorem`

Dependencies: D149

Assumptions:
- eqangle(b,c2,b1,c2,c2,m2,b1,c2)

Assertions:
- equation_class Yuclid::SinOrDist(b,c2,b1,b1,c2,m2)

### D151 `ar:angle chasing:directed_angle`

Dependencies: D085, D100, D139, D144, D147

Assumptions:
- para(a,c1,b,c1): (1/1)*∠(a-c1) + (-1/1)*∠(b-c1) = 0
- para(a,c1,c1,c2): (1/1)*∠(a-c1) + (-1/1)*∠(c1-c2) = 0
- para(c1,c2,c1,m2): (1/1)*∠(c1-c2) + (-1/1)*∠(c1-m2) = 0
- para(a,m2,c1,m2): (1/1)*∠(a-m2) + (-1/1)*∠(c1-m2) = 0
- para(b,c1,b,m2): (1/1)*∠(b-c1) + (-1/1)*∠(b-m2) = 0

Assertions:
- eqangle(a,m2,b1,m2,b,m2,b1,m2): (-1/1)*∠(a-m2) + (1/1)*∠(b-m2) = 0

### D152 `internal_theorem`

Dependencies: D151

Assumptions:
- eqangle(a,m2,b1,m2,b,m2,b1,m2)

Assertions:
- equation_class Yuclid::SinOrDist(a,m2,b1,b,m2,b1)

### D153 `ar:angle chasing:directed_angle`

Dependencies: D085, D100, D138, D139, D147

Assumptions:
- para(a,c1,b,c1): (1/1)*∠(a-c1) + (-1/1)*∠(b-c1) = 0
- para(a,c1,c1,c2): (1/1)*∠(a-c1) + (-1/1)*∠(c1-c2) = 0
- para(c1,m2,c2,m2): (1/1)*∠(c1-m2) + (-1/1)*∠(c2-m2) = 0
- para(c1,c2,c1,m2): (1/1)*∠(c1-c2) + (-1/1)*∠(c1-m2) = 0
- para(b,c1,b,m2): (1/1)*∠(b-c1) + (-1/1)*∠(b-m2) = 0

Assertions:
- eqangle(b,m2,b1,m2,c2,m2,b1,m2): (-1/1)*∠(b-m2) + (1/1)*∠(c2-m2) = 0

### D154 `internal_theorem`

Dependencies: D153

Assumptions:
- eqangle(b,m2,b1,m2,c2,m2,b1,m2)

Assertions:
- equation_class Yuclid::SinOrDist(b,m2,b1,b1,m2,c2)

### D155 `ar:angle chasing:directed_angle`

Dependencies: D085, D100, D139, D144, D147

Assumptions:
- para(a,c1,b,c1): (1/1)*∠(a-c1) + (-1/1)*∠(b-c1) = 0
- para(a,c1,c1,c2): (1/1)*∠(a-c1) + (-1/1)*∠(c1-c2) = 0
- para(c1,c2,c1,m2): (1/1)*∠(c1-c2) + (-1/1)*∠(c1-m2) = 0
- para(a,m2,c1,m2): (1/1)*∠(a-m2) + (-1/1)*∠(c1-m2) = 0
- para(b,c1,b,m2): (1/1)*∠(b-c1) + (-1/1)*∠(b-m2) = 0

Assertions:
- eqangle(a,m2,c,m2,b,m2,c,m2): (-1/1)*∠(a-m2) + (1/1)*∠(b-m2) = 0

### D156 `internal_theorem`

Dependencies: D155

Assumptions:
- eqangle(a,m2,c,m2,b,m2,c,m2)

Assertions:
- equation_class Yuclid::SinOrDist(a,m2,c,b,m2,c)

### D157 `ar:angle chasing:directed_angle`

Dependencies: D087, D088, D090, D093, D134, D135

Assumptions:
- para(a,b1,c,b1): (1/1)*∠(a-b1) + (-1/1)*∠(c-b1) = 0
- para(a,c,a,b1): (1/1)*∠(a-c) + (-1/1)*∠(a-b1) = 0
- para(a,c,a,b2): (1/1)*∠(a-c) + (-1/1)*∠(a-b2) = 0
- para(c,b1,b1,b2): (1/1)*∠(c-b1) + (-1/1)*∠(b1-b2) = 0
- para(b1,m1,m1,b2): (1/1)*∠(b1-m1) + (-1/1)*∠(m1-b2) = 0
- para(b1,m1,b1,b2): (1/1)*∠(b1-m1) + (-1/1)*∠(b1-b2) = 0

Assertions:
- eqangle(a,b2,b2,m2,m1,b2,b2,m2): (-1/1)*∠(a-b2) + (1/1)*∠(m1-b2) = 0

### D158 `internal_theorem`

Dependencies: D157

Assumptions:
- eqangle(a,b2,b2,m2,m1,b2,b2,m2)

Assertions:
- equation_class Yuclid::SinOrDist(a,b2,m2,m1,b2,m2)

### D159 `ar:angle chasing:directed_angle`

Dependencies: D085, D100, D139, D144, D147

Assumptions:
- para(a,c1,b,c1): (1/1)*∠(a-c1) + (-1/1)*∠(b-c1) = 0
- para(a,c1,c1,c2): (1/1)*∠(a-c1) + (-1/1)*∠(c1-c2) = 0
- para(c1,c2,c1,m2): (1/1)*∠(c1-c2) + (-1/1)*∠(c1-m2) = 0
- para(a,m2,c1,m2): (1/1)*∠(a-m2) + (-1/1)*∠(c1-m2) = 0
- para(b,c1,b,m2): (1/1)*∠(b-c1) + (-1/1)*∠(b-m2) = 0

Assertions:
- eqangle(a,m2,m1,m2,b,m2,m1,m2): (-1/1)*∠(a-m2) + (1/1)*∠(b-m2) = 0

### D160 `internal_theorem`

Dependencies: D159

Assumptions:
- eqangle(a,m2,m1,m2,b,m2,m1,m2)

Assertions:
- equation_class Yuclid::SinOrDist(a,m2,m1,b,m2,m1)

### D161 `ar:angle chasing:directed_angle`

Dependencies: D015, D078, D131, D134

Assumptions:
- perp(b,b1,b,b2): (1/1)*∠(b-b1) + (-1/1)*∠(b-b2) = 0
- eqangle(p,b1,b1,m1,p,m1,p,b1): (-2/1)*∠(p-b1) + (1/1)*∠(p-m1) + (1/1)*∠(b1-m1) = 0
- eqangle(p,b2,m1,b2,p,m1,p,b2): (1/1)*∠(p-m1) + (-2/1)*∠(p-b2) + (1/1)*∠(m1-b2) = 0
- para(b1,m1,m1,b2): (1/1)*∠(b1-m1) + (-1/1)*∠(m1-b2) = 0

Assertions:
- eqangle(b,b1,b,b2,p,b1,p,b2): (-1/1)*∠(b-b1) + (1/1)*∠(b-b2) + (1/1)*∠(p-b1) + (-1/1)*∠(p-b2) = 0

### D162 `dd:r04`

Dependencies: D161, D052

Assumptions:
- eqangle(b,b1,b,b2,p,b1,p,b2)
- ncoll(p,b1,b2)

Assertions:
- cyclic(b,p,b1,b2)

### D163 `dd:r03`

Dependencies: D162

Assumptions:
- cyclic(b,p,b1,b2)

Assertions:
- eqangle(b,p,p,b2,b,b1,b1,b2)

### D164 `ar:angle chasing:directed_angle`

Dependencies: D016, D075, D133, D138

Assumptions:
- perp(c,c1,c,c2): (1/1)*∠(c-c1) + (-1/1)*∠(c-c2) = 0
- eqangle(p,c1,c1,m2,p,m2,p,c1): (-2/1)*∠(p-c1) + (1/1)*∠(p-m2) + (1/1)*∠(c1-m2) = 0
- eqangle(p,c2,c2,m2,p,m2,p,c2): (-2/1)*∠(p-c2) + (1/1)*∠(p-m2) + (1/1)*∠(c2-m2) = 0
- para(c1,m2,c2,m2): (1/1)*∠(c1-m2) + (-1/1)*∠(c2-m2) = 0

Assertions:
- eqangle(c,c1,c,c2,p,c1,p,c2): (-1/1)*∠(c-c1) + (1/1)*∠(c-c2) + (1/1)*∠(p-c1) + (-1/1)*∠(p-c2) = 0

### D165 `dd:r04`

Dependencies: D164, D053

Assumptions:
- eqangle(c,c1,c,c2,p,c1,p,c2)
- ncoll(c,c1,c2)

Assertions:
- cyclic(c,p,c1,c2)

### D166 `dd:r03`

Dependencies: D165

Assumptions:
- cyclic(c,p,c1,c2)

Assertions:
- eqangle(c,p,c,c2,p,c1,c1,c2)

### D167 `ar:angle chasing:directed_angle`

Dependencies: D075, D133, D138

Assumptions:
- eqangle(p,c1,c1,m2,p,m2,p,c1): (-2/1)*∠(p-c1) + (1/1)*∠(p-m2) + (1/1)*∠(c1-m2) = 0
- eqangle(p,c2,c2,m2,p,m2,p,c2): (-2/1)*∠(p-c2) + (1/1)*∠(p-m2) + (1/1)*∠(c2-m2) = 0
- para(c1,m2,c2,m2): (1/1)*∠(c1-m2) + (-1/1)*∠(c2-m2) = 0

Assertions:
- perp(p,c1,p,c2): (1/1)*∠(p-c1) + (-1/1)*∠(p-c2) = 0

### D168 `internal_theorem`

Dependencies: D054, D055, D167

Assumptions:
- diff(p,c2)
- diff(p,c1)
- perp(p,c1,p,c2)

Assertions:
- equation_class Yuclid::SquaredDist(p,c1,p,c2,c1,c2)

### D169 `ar:angle chasing:directed_angle`

Dependencies: D078, D131, D134

Assumptions:
- eqangle(p,b1,b1,m1,p,m1,p,b1): (-2/1)*∠(p-b1) + (1/1)*∠(p-m1) + (1/1)*∠(b1-m1) = 0
- eqangle(p,b2,m1,b2,p,m1,p,b2): (1/1)*∠(p-m1) + (-2/1)*∠(p-b2) + (1/1)*∠(m1-b2) = 0
- para(b1,m1,m1,b2): (1/1)*∠(b1-m1) + (-1/1)*∠(m1-b2) = 0

Assertions:
- perp(p,b1,p,b2): (1/1)*∠(p-b1) + (-1/1)*∠(p-b2) = 0

### D170 `internal_theorem`

Dependencies: D056, D057, D169

Assumptions:
- diff(p,b1)
- diff(p,b2)
- perp(p,b1,p,b2)

Assertions:
- equation_class Yuclid::SquaredDist(p,b1,p,b2,b1,b2)

### D171 `ar:squared lengths chasing:squared_distance`

Dependencies: D006, D095, D113, D136, D137, D170

Assumptions:
- cong(p,m1,b1,m1): (1/1)*|p-m1|^2 + (-1/1)*|b1-m1|^2 = 0
- cong(b1,m1,m1,b2): (1/1)*|b1-m1|^2 + (-1/1)*|m1-b2|^2 = 0
- equation_class Yuclid::SquaredDist(b,b1,b,b2,b1,b2): (1/1)*|b-b1|^2 + (1/1)*|b-b2|^2 + (-1/1)*|b1-b2|^2 = 0
- equation_class Yuclid::SquaredDist(b,b1,b,m1,b,b2,b1,b2): (1/1)*|b-b1|^2 + (-2/1)*|b-m1|^2 + (1/1)*|b-b2|^2 + (-1/2)*|b1-b2|^2 = 0
- equation_class Yuclid::SquaredDist(p,b1,p,m1,p,b2,b1,b2): (1/1)*|p-b1|^2 + (-2/1)*|p-m1|^2 + (1/1)*|p-b2|^2 + (-1/2)*|b1-b2|^2 = 0
- equation_class Yuclid::SquaredDist(p,b1,p,b2,b1,b2): (1/1)*|p-b1|^2 + (1/1)*|p-b2|^2 + (-1/1)*|b1-b2|^2 = 0

Assertions:
- cong(b,m1,m1,b2): (1/1)*|b-m1|^2 + (-1/1)*|m1-b2|^2 = 0

### D172 `dd:r13`

Dependencies: D171

Assumptions:
- cong(b,m1,m1,b2)

Assertions:
- eqangle(b,b2,m1,b2,b,m1,b,b2)

### D173 `ar:squared lengths chasing:squared_distance`

Dependencies: D114, D140, D141, D168

Assumptions:
- equation_class Yuclid::SquaredDist(c,c1,c,c2,c1,c2): (1/1)*|c-c1|^2 + (1/1)*|c-c2|^2 + (-1/1)*|c1-c2|^2 = 0
- equation_class Yuclid::SquaredDist(c,c1,c,c2,c,m2,c1,c2): (1/1)*|c-c1|^2 + (1/1)*|c-c2|^2 + (-2/1)*|c-m2|^2 + (-1/2)*|c1-c2|^2 = 0
- equation_class Yuclid::SquaredDist(p,c1,p,c2,p,m2,c1,c2): (1/1)*|p-c1|^2 + (1/1)*|p-c2|^2 + (-2/1)*|p-m2|^2 + (-1/2)*|c1-c2|^2 = 0
- equation_class Yuclid::SquaredDist(p,c1,p,c2,c1,c2): (1/1)*|p-c1|^2 + (1/1)*|p-c2|^2 + (-1/1)*|c1-c2|^2 = 0

Assertions:
- cong(c,m2,p,m2): (1/1)*|c-m2|^2 + (-1/1)*|p-m2|^2 = 0

### D174 `dd:r13`

Dependencies: D173

Assumptions:
- cong(c,m2,p,m2)

Assertions:
- eqangle(c,p,p,m2,c,m2,c,p)

### D175 `ar:angle chasing:directed_angle`

Dependencies: D093, D135

Assumptions:
- para(c,b1,b1,b2): (1/1)*∠(c-b1) + (-1/1)*∠(b1-b2) = 0
- para(b1,m1,b1,b2): (1/1)*∠(b1-m1) + (-1/1)*∠(b1-b2) = 0

Assertions:
- para(c,b1,b1,m1): (1/1)*∠(c-b1) + (-1/1)*∠(b1-m1) = 0

### D176 `dd:r28`

Dependencies: D175

Assumptions:
- para(c,b1,b1,m1)

Assertions:
- coll(c,b1,m1)

### D177 `dd:r82`

Dependencies: D176, D040, D039, D037

Assumptions:
- coll(c,b1,m1)
- diff(b1,m1)
- diff(c,m1)
- diff(c,b1)

Assertions:
- para(c,m1,b1,m1)

### D178 `ar:angle chasing:directed_angle`

Dependencies: D087, D093, D135

Assumptions:
- para(a,b1,c,b1): (1/1)*∠(a-b1) + (-1/1)*∠(c-b1) = 0
- para(c,b1,b1,b2): (1/1)*∠(c-b1) + (-1/1)*∠(b1-b2) = 0
- para(b1,m1,b1,b2): (1/1)*∠(b1-m1) + (-1/1)*∠(b1-b2) = 0

Assertions:
- para(a,b1,b1,m1): (1/1)*∠(a-b1) + (-1/1)*∠(b1-m1) = 0

### D179 `dd:r28`

Dependencies: D178

Assumptions:
- para(a,b1,b1,m1)

Assertions:
- coll(a,b1,m1)

### D180 `dd:r82`

Dependencies: D179, D035, D038, D040

Assumptions:
- coll(a,b1,m1)
- diff(a,b1)
- diff(a,m1)
- diff(b1,m1)

Assertions:
- para(a,b1,a,m1)

### D181 `ar:angle chasing:directed_angle`

Dependencies: D087, D093, D134, D135, D180

Assumptions:
- para(a,b1,c,b1): (1/1)*∠(a-b1) + (-1/1)*∠(c-b1) = 0
- para(c,b1,b1,b2): (1/1)*∠(c-b1) + (-1/1)*∠(b1-b2) = 0
- para(b1,m1,m1,b2): (1/1)*∠(b1-m1) + (-1/1)*∠(m1-b2) = 0
- para(b1,m1,b1,b2): (1/1)*∠(b1-m1) + (-1/1)*∠(b1-b2) = 0
- para(a,b1,a,m1): (1/1)*∠(a-b1) + (-1/1)*∠(a-m1) = 0

Assertions:
- eqangle(a,m1,m1,m2,m1,b2,m1,m2): (-1/1)*∠(a-m1) + (1/1)*∠(m1-b2) = 0

### D182 `internal_theorem`

Dependencies: D181

Assumptions:
- eqangle(a,m1,m1,m2,m1,b2,m1,m2)

Assertions:
- equation_class Yuclid::SinOrDist(a,m1,m2,b2,m1,m2)

### D183 `ar:angle chasing:directed_angle`

Dependencies: D010, D016, D075, D086, D100, D139, D166, D174

Assumptions:
- eqangle(b,c,c,c1,c,c1,a,c): (-1/1)*∠(a-c) + (-1/1)*∠(b-c) + (2/1)*∠(c-c1) = 0
- perp(c,c1,c,c2): (1/1)*∠(c-c1) + (-1/1)*∠(c-c2) = 0
- eqangle(p,c1,c1,m2,p,m2,p,c1): (-2/1)*∠(p-c1) + (1/1)*∠(p-m2) + (1/1)*∠(c1-m2) = 0
- para(a,b,a,c1): (1/1)*∠(a-b) + (-1/1)*∠(a-c1) = 0
- para(a,c1,c1,c2): (1/1)*∠(a-c1) + (-1/1)*∠(c1-c2) = 0
- para(c1,c2,c1,m2): (1/1)*∠(c1-c2) + (-1/1)*∠(c1-m2) = 0
- eqangle(c,p,c,c2,p,c1,c1,c2): (-1/1)*∠(c-p) + (1/1)*∠(c-c2) + (1/1)*∠(p-c1) + (-1/1)*∠(c1-c2) = 0
- eqangle(c,p,p,m2,c,m2,c,p): (-2/1)*∠(c-p) + (1/1)*∠(c-m2) + (1/1)*∠(p-m2) = 0

Assertions:
- eqangle(a,b,b,c,a,c,c,m2): (-1/1)*∠(a-b) + (1/1)*∠(a-c) + (1/1)*∠(b-c) + (-1/1)*∠(c-m2) = 0

### D184 `internal_theorem`

Dependencies: D183

Assumptions:
- eqangle(a,b,b,c,a,c,c,m2)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,c,a,c,m2)

### D185 `ar:angle chasing:directed_angle`

Dependencies: D087, D093, D135, D177, D180

Assumptions:
- para(a,b1,c,b1): (1/1)*∠(a-b1) + (-1/1)*∠(c-b1) = 0
- para(c,b1,b1,b2): (1/1)*∠(c-b1) + (-1/1)*∠(b1-b2) = 0
- para(b1,m1,b1,b2): (1/1)*∠(b1-m1) + (-1/1)*∠(b1-b2) = 0
- para(c,m1,b1,m1): (1/1)*∠(c-m1) + (-1/1)*∠(b1-m1) = 0
- para(a,b1,a,m1): (1/1)*∠(a-b1) + (-1/1)*∠(a-m1) = 0

Assertions:
- eqangle(a,m1,p,m1,c,m1,p,m1): (-1/1)*∠(a-m1) + (1/1)*∠(c-m1) = 0

### D186 `ar:angle chasing:directed_angle`

Dependencies: D009, D010, D015, D016, D075, D086, D087, D088, D093, D100, D134, D135, D139, D166, D172, D174

Assumptions:
- eqangle(b,c,b,b1,b,b1,a,b): (-1/1)*∠(a-b) + (-1/1)*∠(b-c) + (2/1)*∠(b-b1) = 0
- eqangle(b,c,c,c1,c,c1,a,c): (-1/1)*∠(a-c) + (-1/1)*∠(b-c) + (2/1)*∠(c-c1) = 0
- perp(b,b1,b,b2): (1/1)*∠(b-b1) + (-1/1)*∠(b-b2) = 0
- perp(c,c1,c,c2): (1/1)*∠(c-c1) + (-1/1)*∠(c-c2) = 0
- eqangle(p,c1,c1,m2,p,m2,p,c1): (-2/1)*∠(p-c1) + (1/1)*∠(p-m2) + (1/1)*∠(c1-m2) = 0
- para(a,b,a,c1): (1/1)*∠(a-b) + (-1/1)*∠(a-c1) = 0
- para(a,b1,c,b1): (1/1)*∠(a-b1) + (-1/1)*∠(c-b1) = 0
- para(a,c,a,b1): (1/1)*∠(a-c) + (-1/1)*∠(a-b1) = 0
- para(c,b1,b1,b2): (1/1)*∠(c-b1) + (-1/1)*∠(b1-b2) = 0
- para(a,c1,c1,c2): (1/1)*∠(a-c1) + (-1/1)*∠(c1-c2) = 0
- para(b1,m1,m1,b2): (1/1)*∠(b1-m1) + (-1/1)*∠(m1-b2) = 0
- para(b1,m1,b1,b2): (1/1)*∠(b1-m1) + (-1/1)*∠(b1-b2) = 0
- para(c1,c2,c1,m2): (1/1)*∠(c1-c2) + (-1/1)*∠(c1-m2) = 0
- eqangle(c,p,c,c2,p,c1,c1,c2): (-1/1)*∠(c-p) + (1/1)*∠(c-c2) + (1/1)*∠(p-c1) + (-1/1)*∠(c1-c2) = 0
- eqangle(b,b2,m1,b2,b,m1,b,b2): (1/1)*∠(b-m1) + (-2/1)*∠(b-b2) + (1/1)*∠(m1-b2) = 0
- eqangle(c,p,p,m2,c,m2,c,p): (-2/1)*∠(c-p) + (1/1)*∠(c-m2) + (1/1)*∠(p-m2) = 0

Assertions:
- eqangle(b,c,c,m2,b,m1,b,c): (-2/1)*∠(b-c) + (1/1)*∠(b-m1) + (1/1)*∠(c-m2) = 0

### D187 `internal_theorem`

Dependencies: D186

Assumptions:
- eqangle(b,c,c,m2,b,m1,b,c)

Assertions:
- equation_class Yuclid::SinOrDist(b,c,m2,c,b,m1)

### D188 `ar:angle chasing:directed_angle`

Dependencies: D010, D016, D075, D086, D090, D096, D100, D139, D166, D174

Assumptions:
- eqangle(b,c,c,c1,c,c1,a,c): (-1/1)*∠(a-c) + (-1/1)*∠(b-c) + (2/1)*∠(c-c1) = 0
- perp(c,c1,c,c2): (1/1)*∠(c-c1) + (-1/1)*∠(c-c2) = 0
- eqangle(p,c1,c1,m2,p,m2,p,c1): (-2/1)*∠(p-c1) + (1/1)*∠(p-m2) + (1/1)*∠(c1-m2) = 0
- para(a,b,a,c1): (1/1)*∠(a-b) + (-1/1)*∠(a-c1) = 0
- para(a,c,a,b2): (1/1)*∠(a-c) + (-1/1)*∠(a-b2) = 0
- para(a,b,a,c2): (1/1)*∠(a-b) + (-1/1)*∠(a-c2) = 0
- para(a,c1,c1,c2): (1/1)*∠(a-c1) + (-1/1)*∠(c1-c2) = 0
- para(c1,c2,c1,m2): (1/1)*∠(c1-c2) + (-1/1)*∠(c1-m2) = 0
- eqangle(c,p,c,c2,p,c1,c1,c2): (-1/1)*∠(c-p) + (1/1)*∠(c-c2) + (1/1)*∠(p-c1) + (-1/1)*∠(c1-c2) = 0
- eqangle(c,p,p,m2,c,m2,c,p): (-2/1)*∠(c-p) + (1/1)*∠(c-m2) + (1/1)*∠(p-m2) = 0

Assertions:
- eqangle(b,c,c,m2,a,c2,a,b2): (-1/1)*∠(a-b2) + (1/1)*∠(a-c2) + (-1/1)*∠(b-c) + (1/1)*∠(c-m2) = 0

### D189 `internal_theorem`

Dependencies: D188

Assumptions:
- eqangle(b,c,c,m2,a,c2,a,b2)

Assertions:
- equation_class Yuclid::SinOrDist(b,c,m2,b2,a,c2)

### D190 `ar:angle chasing:directed_angle`

Dependencies: D009, D015, D085, D086, D134, D147, D172, D177

Assumptions:
- eqangle(b,c,b,b1,b,b1,a,b): (-1/1)*∠(a-b) + (-1/1)*∠(b-c) + (2/1)*∠(b-b1) = 0
- perp(b,b1,b,b2): (1/1)*∠(b-b1) + (-1/1)*∠(b-b2) = 0
- para(a,c1,b,c1): (1/1)*∠(a-c1) + (-1/1)*∠(b-c1) = 0
- para(a,b,a,c1): (1/1)*∠(a-b) + (-1/1)*∠(a-c1) = 0
- para(b1,m1,m1,b2): (1/1)*∠(b1-m1) + (-1/1)*∠(m1-b2) = 0
- para(b,c1,b,m2): (1/1)*∠(b-c1) + (-1/1)*∠(b-m2) = 0
- eqangle(b,b2,m1,b2,b,m1,b,b2): (1/1)*∠(b-m1) + (-2/1)*∠(b-b2) + (1/1)*∠(m1-b2) = 0
- para(c,m1,b1,m1): (1/1)*∠(c-m1) + (-1/1)*∠(b1-m1) = 0

Assertions:
- eqangle(b,c,c,m1,b,m1,b,m2): (-1/1)*∠(b-c) + (1/1)*∠(b-m1) + (-1/1)*∠(b-m2) + (1/1)*∠(c-m1) = 0

### D191 `internal_theorem`

Dependencies: D190

Assumptions:
- eqangle(b,c,c,m1,b,m1,b,m2)

Assertions:
- equation_class Yuclid::SinOrDist(b,c,m1,m1,b,m2)

### D192 `ar:ratio chasing:sine_squared+squared_distance` [SINE-DISTANCE BRIDGE]

Dependencies: D104, D106, D108, D110, D115, D117, D118, D119, D120, D121, D122, D123, D129, D150, D152, D154, D156, D173, D184, D189

Assumptions:
- equation_class Yuclid::SinOrDist(a,c2,b1,b,c2,b1): (1/1)*\sin² ∠(a c2 b1) + (-1/1)*\sin² ∠(b c2 b1) = 0
- equation_class Yuclid::SinOrDist(b1,a,c2,b2,a,c2): (1/1)*\sin² ∠(b1 a c2) + (-1/1)*\sin² ∠(b2 a c2) = 0
- equation_class Yuclid::SinOrDist(b,a,c,b2,a,c2): (1/1)*\sin² ∠(b a c) + (-1/1)*\sin² ∠(b2 a c2) = 0
- equation_class Yuclid::SinOrDist(c,a,m2,b1,a,m2): (1/1)*\sin² ∠(c a m2) + (-1/1)*\sin² ∠(b1 a m2) = 0
- equation_class Yuclid::SinOrDist(a,b,c,b,a,c,a,c,b,c): (1/1)*\sin² ∠(a b c) + (-1/1)*\sin² ∠(b a c) + (-1/1)*|a-c|^2 + (1/1)*|b-c|^2 = 0
- equation_class Yuclid::SinOrDist(a,b1,c2,b1,a,c2,a,c2,b1,c2): (1/1)*\sin² ∠(a b1 c2) + (-1/1)*\sin² ∠(b1 a c2) + (-1/1)*|a-c2|^2 + (1/1)*|b1-c2|^2 = 0
- equation_class Yuclid::SinOrDist(a,b1,c2,a,c2,b1,a,b1,a,c2): (1/1)*\sin² ∠(a b1 c2) + (-1/1)*\sin² ∠(a c2 b1) + (1/1)*|a-b1|^2 + (-1/1)*|a-c2|^2 = 0
- equation_class Yuclid::SinOrDist(a,c,m2,c,a,m2,a,m2,c,m2): (1/1)*\sin² ∠(a c m2) + (-1/1)*\sin² ∠(c a m2) + (-1/1)*|a-m2|^2 + (1/1)*|c-m2|^2 = 0
- equation_class Yuclid::SinOrDist(a,c,m2,a,m2,c,a,c,a,m2): (1/1)*\sin² ∠(a c m2) + (-1/1)*\sin² ∠(a m2 c) + (1/1)*|a-c|^2 + (-1/1)*|a-m2|^2 = 0
- equation_class Yuclid::SinOrDist(b,c,m2,b,m2,c,b,c,b,m2): (1/1)*\sin² ∠(b c m2) + (-1/1)*\sin² ∠(b m2 c) + (1/1)*|b-c|^2 + (-1/1)*|b-m2|^2 = 0
- equation_class Yuclid::SinOrDist(a,b1,m2,b1,a,m2,a,m2,b1,m2): (1/1)*\sin² ∠(a b1 m2) + (-1/1)*\sin² ∠(b1 a m2) + (-1/1)*|a-m2|^2 + (1/1)*|b1-m2|^2 = 0
- equation_class Yuclid::SinOrDist(a,b1,m2,a,m2,b1,a,b1,a,m2): (1/1)*\sin² ∠(a b1 m2) + (-1/1)*\sin² ∠(a m2 b1) + (1/1)*|a-b1|^2 + (-1/1)*|a-m2|^2 = 0
- equation_class Yuclid::SinOrDist(b1,c2,m2,b1,m2,c2,b1,c2,b1,m2): (1/1)*\sin² ∠(b1 c2 m2) + (-1/1)*\sin² ∠(b1 m2 c2) + (1/1)*|b1-c2|^2 + (-1/1)*|b1-m2|^2 = 0
- equation_class Yuclid::SinOrDist(b,c2,b1,b1,c2,m2): (1/1)*\sin² ∠(b c2 b1) + (-1/1)*\sin² ∠(b1 c2 m2) = 0
- equation_class Yuclid::SinOrDist(a,m2,b1,b,m2,b1): (1/1)*\sin² ∠(a m2 b1) + (-1/1)*\sin² ∠(b m2 b1) = 0
- equation_class Yuclid::SinOrDist(b,m2,b1,b1,m2,c2): (1/1)*\sin² ∠(b m2 b1) + (-1/1)*\sin² ∠(b1 m2 c2) = 0
- equation_class Yuclid::SinOrDist(a,m2,c,b,m2,c): (1/1)*\sin² ∠(a m2 c) + (-1/1)*\sin² ∠(b m2 c) = 0
- cong(c,m2,p,m2): (1/1)*|c-m2|^2 + (-1/1)*|p-m2|^2 = 0
- equation_class Yuclid::SinOrDist(a,b,c,a,c,m2): (1/1)*\sin² ∠(a b c) + (-1/1)*\sin² ∠(a c m2) = 0
- equation_class Yuclid::SinOrDist(b,c,m2,b2,a,c2): (1/1)*\sin² ∠(b c m2) + (-1/1)*\sin² ∠(b2 a c2) = 0

Assertions:
- eqratio(a,m2,p,m2,p,m2,b,m2): (1/1)*|a-m2|^2 + (1/1)*|b-m2|^2 + (-2/1)*|p-m2|^2 = 0

### D193 `dd:r63`

Dependencies: D192, D148, D021

Assumptions:
- eqratio(a,m2,p,m2,p,m2,b,m2)
- eqangle(a,m2,p,m2,b,m2,p,m2)
- sameclock(a,m2,p,p,b,m2)

Assertions:
- simtrir(a,p,m2,p,b,m2)

### D194 `dd:r53`

Dependencies: D193, D020

Assumptions:
- simtrir(a,p,m2,p,b,m2)
- sameclock(p,a,m2,b,m2,p)

Assertions:
- eqangle(b,p,p,m2,a,m2,a,p)

### D195 `ar:ratio chasing:sine_squared+squared_distance` [SINE-DISTANCE BRIDGE]

Dependencies: D006, D095, D104, D106, D110, D112, D116, D117, D118, D122, D123, D124, D125, D126, D127, D128, D129, D150, D152, D154, D158, D160, D171, D182, D187, D189, D191

Assumptions:
- cong(p,m1,b1,m1): (1/1)*|p-m1|^2 + (-1/1)*|b1-m1|^2 = 0
- cong(b1,m1,m1,b2): (1/1)*|b1-m1|^2 + (-1/1)*|m1-b2|^2 = 0
- equation_class Yuclid::SinOrDist(a,c2,b1,b,c2,b1): (1/1)*\sin² ∠(a c2 b1) + (-1/1)*\sin² ∠(b c2 b1) = 0
- equation_class Yuclid::SinOrDist(b1,a,c2,b2,a,c2): (1/1)*\sin² ∠(b1 a c2) + (-1/1)*\sin² ∠(b2 a c2) = 0
- equation_class Yuclid::SinOrDist(c,a,m2,b1,a,m2): (1/1)*\sin² ∠(c a m2) + (-1/1)*\sin² ∠(b1 a m2) = 0
- equation_class Yuclid::SinOrDist(c,a,m2,b2,a,m2): (1/1)*\sin² ∠(c a m2) + (-1/1)*\sin² ∠(b2 a m2) = 0
- equation_class Yuclid::SinOrDist(b,c,m1,c,b,m1,b,m1,c,m1): (1/1)*\sin² ∠(b c m1) + (-1/1)*\sin² ∠(c b m1) + (-1/1)*|b-m1|^2 + (1/1)*|c-m1|^2 = 0
- equation_class Yuclid::SinOrDist(a,b1,c2,b1,a,c2,a,c2,b1,c2): (1/1)*\sin² ∠(a b1 c2) + (-1/1)*\sin² ∠(b1 a c2) + (-1/1)*|a-c2|^2 + (1/1)*|b1-c2|^2 = 0
- equation_class Yuclid::SinOrDist(a,b1,c2,a,c2,b1,a,b1,a,c2): (1/1)*\sin² ∠(a b1 c2) + (-1/1)*\sin² ∠(a c2 b1) + (1/1)*|a-b1|^2 + (-1/1)*|a-c2|^2 = 0
- equation_class Yuclid::SinOrDist(a,b1,m2,b1,a,m2,a,m2,b1,m2): (1/1)*\sin² ∠(a b1 m2) + (-1/1)*\sin² ∠(b1 a m2) + (-1/1)*|a-m2|^2 + (1/1)*|b1-m2|^2 = 0
- equation_class Yuclid::SinOrDist(a,b1,m2,a,m2,b1,a,b1,a,m2): (1/1)*\sin² ∠(a b1 m2) + (-1/1)*\sin² ∠(a m2 b1) + (1/1)*|a-b1|^2 + (-1/1)*|a-m2|^2 = 0
- equation_class Yuclid::SinOrDist(a,m1,m2,a,m2,m1,a,m1,a,m2): (1/1)*\sin² ∠(a m1 m2) + (-1/1)*\sin² ∠(a m2 m1) + (1/1)*|a-m1|^2 + (-1/1)*|a-m2|^2 = 0
- equation_class Yuclid::SinOrDist(b,m1,m2,m1,b,m2,b,m2,m1,m2): (1/1)*\sin² ∠(b m1 m2) + (-1/1)*\sin² ∠(m1 b m2) + (-1/1)*|b-m2|^2 + (1/1)*|m1-m2|^2 = 0
- equation_class Yuclid::SinOrDist(b,m1,m2,b,m2,m1,b,m1,b,m2): (1/1)*\sin² ∠(b m1 m2) + (-1/1)*\sin² ∠(b m2 m1) + (1/1)*|b-m1|^2 + (-1/1)*|b-m2|^2 = 0
- equation_class Yuclid::SinOrDist(a,b2,m2,b2,a,m2,a,m2,b2,m2): (1/1)*\sin² ∠(a b2 m2) + (-1/1)*\sin² ∠(b2 a m2) + (-1/1)*|a-m2|^2 + (1/1)*|b2-m2|^2 = 0
- equation_class Yuclid::SinOrDist(m1,b2,m2,b2,m1,m2,m1,m2,b2,m2): (1/1)*\sin² ∠(m1 b2 m2) + (-1/1)*\sin² ∠(b2 m1 m2) + (-1/1)*|m1-m2|^2 + (1/1)*|b2-m2|^2 = 0
- equation_class Yuclid::SinOrDist(b1,c2,m2,b1,m2,c2,b1,c2,b1,m2): (1/1)*\sin² ∠(b1 c2 m2) + (-1/1)*\sin² ∠(b1 m2 c2) + (1/1)*|b1-c2|^2 + (-1/1)*|b1-m2|^2 = 0
- equation_class Yuclid::SinOrDist(b,c2,b1,b1,c2,m2): (1/1)*\sin² ∠(b c2 b1) + (-1/1)*\sin² ∠(b1 c2 m2) = 0
- equation_class Yuclid::SinOrDist(a,m2,b1,b,m2,b1): (1/1)*\sin² ∠(a m2 b1) + (-1/1)*\sin² ∠(b m2 b1) = 0
- equation_class Yuclid::SinOrDist(b,m2,b1,b1,m2,c2): (1/1)*\sin² ∠(b m2 b1) + (-1/1)*\sin² ∠(b1 m2 c2) = 0
- equation_class Yuclid::SinOrDist(a,b2,m2,m1,b2,m2): (1/1)*\sin² ∠(a b2 m2) + (-1/1)*\sin² ∠(m1 b2 m2) = 0
- equation_class Yuclid::SinOrDist(a,m2,m1,b,m2,m1): (1/1)*\sin² ∠(a m2 m1) + (-1/1)*\sin² ∠(b m2 m1) = 0
- cong(b,m1,m1,b2): (1/1)*|b-m1|^2 + (-1/1)*|m1-b2|^2 = 0
- equation_class Yuclid::SinOrDist(a,m1,m2,b2,m1,m2): (1/1)*\sin² ∠(a m1 m2) + (-1/1)*\sin² ∠(b2 m1 m2) = 0
- equation_class Yuclid::SinOrDist(b,c,m2,c,b,m1): (1/1)*\sin² ∠(b c m2) + (-1/1)*\sin² ∠(c b m1) = 0
- equation_class Yuclid::SinOrDist(b,c,m2,b2,a,c2): (1/1)*\sin² ∠(b c m2) + (-1/1)*\sin² ∠(b2 a c2) = 0
- equation_class Yuclid::SinOrDist(b,c,m1,m1,b,m2): (1/1)*\sin² ∠(b c m1) + (-1/1)*\sin² ∠(m1 b m2) = 0

Assertions:
- eqratio(a,m1,p,m1,p,m1,c,m1): (1/1)*|a-m1|^2 + (1/1)*|c-m1|^2 + (-2/1)*|p-m1|^2 = 0

### D196 `dd:r63`

Dependencies: D195, D185, D026

Assumptions:
- eqratio(a,m1,p,m1,p,m1,c,m1)
- eqangle(a,m1,p,m1,c,m1,p,m1)
- sameclock(p,m1,a,c,p,m1)

Assertions:
- simtrir(a,p,m1,p,c,m1)

### D197 `dd:r53`

Dependencies: D196, D025

Assumptions:
- simtrir(a,p,m1,p,c,m1)
- sameclock(a,p,m1,p,m1,c)

Assertions:
- eqangle(a,p,p,m1,c,m1,c,p)

### D198 `ar:angle chasing:directed_angle`

Dependencies: D009, D010, D011, D012, D016, D075, D081, D084, D086, D087, D088, D093, D100, D131, D134, D144, D163, D166, D177, D194, D197

Assumptions:
- eqangle(b,c,b,b1,b,b1,a,b): (-1/1)*∠(a-b) + (-1/1)*∠(b-c) + (2/1)*∠(b-b1) = 0
- eqangle(b,c,c,c1,c,c1,a,c): (-1/1)*∠(a-c) + (-1/1)*∠(b-c) + (2/1)*∠(c-c1) = 0
- eqangle(b,c,c,o,b,o,b,c): (-2/1)*∠(b-c) + (1/1)*∠(b-o) + (1/1)*∠(c-o) = 0
- eqangle(b,o,c,o,c,o,b,c): (-1/1)*∠(b-c) + (-1/1)*∠(b-o) + (2/1)*∠(c-o) = 0
- perp(c,c1,c,c2): (1/1)*∠(c-c1) + (-1/1)*∠(c-c2) = 0
- eqangle(p,c1,c1,m2,p,m2,p,c1): (-2/1)*∠(p-c1) + (1/1)*∠(p-m2) + (1/1)*∠(c1-m2) = 0
- eqangle(a,b,b,o,a,o,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o) + (1/1)*∠(b-o) = 0
- eqangle(a,c,c,o,a,o,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-o) + (1/1)*∠(c-o) = 0
- para(a,b,a,c1): (1/1)*∠(a-b) + (-1/1)*∠(a-c1) = 0
- para(a,b1,c,b1): (1/1)*∠(a-b1) + (-1/1)*∠(c-b1) = 0
- para(a,c,a,b1): (1/1)*∠(a-c) + (-1/1)*∠(a-b1) = 0
- para(c,b1,b1,b2): (1/1)*∠(c-b1) + (-1/1)*∠(b1-b2) = 0
- para(a,c1,c1,c2): (1/1)*∠(a-c1) + (-1/1)*∠(c1-c2) = 0
- eqangle(p,b2,m1,b2,p,m1,p,b2): (1/1)*∠(p-m1) + (-2/1)*∠(p-b2) + (1/1)*∠(m1-b2) = 0
- para(b1,m1,m1,b2): (1/1)*∠(b1-m1) + (-1/1)*∠(m1-b2) = 0
- para(a,m2,c1,m2): (1/1)*∠(a-m2) + (-1/1)*∠(c1-m2) = 0
- eqangle(b,p,p,b2,b,b1,b1,b2): (-1/1)*∠(b-p) + (1/1)*∠(b-b1) + (1/1)*∠(p-b2) + (-1/1)*∠(b1-b2) = 0
- eqangle(c,p,c,c2,p,c1,c1,c2): (-1/1)*∠(c-p) + (1/1)*∠(c-c2) + (1/1)*∠(p-c1) + (-1/1)*∠(c1-c2) = 0
- para(c,m1,b1,m1): (1/1)*∠(c-m1) + (-1/1)*∠(b1-m1) = 0
- eqangle(b,p,p,m2,a,m2,a,p): (-1/1)*∠(a-p) + (1/1)*∠(a-m2) + (-1/1)*∠(b-p) + (1/1)*∠(p-m2) = 0
- eqangle(a,p,p,m1,c,m1,c,p): (-1/1)*∠(a-p) + (-1/1)*∠(c-p) + (1/1)*∠(c-m1) + (1/1)*∠(p-m1) = 0

Assertions:
- perp(b,p,c,p): (1/1)*∠(b-p) + (-1/1)*∠(c-p) = 0
