# 2010CHNWesternMOp6: Yuclid proof trace

- Certificate: `data/hageo-409-current-native-certified-rerun-2026-08-24-runs/proofs/2010CHNWesternMOp6.json`
- Deductions read: 113
- Order: Yuclid certificate order; every deduction is retained.

## Complete deduction trace

### D000 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(a,c,d)

### D001 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(a,f,g)

### D002 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(b,e,f)

### D003 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(d,e,g)

### D004 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(d,e,h)

### D005 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(b,c,b,e)

### D006 `construction`

Dependencies: none

Assumptions: none

Assertions:
- para(a,h,b,g)

### D007 `construction`

Dependencies: none

Assumptions: none

Assertions:
- perp(a,b,c,f)

### D008 `construction`

Dependencies: none

Assumptions: none

Assertions:
- perp(a,c,b,c)

### D009 `construction`

Dependencies: none

Assumptions: none

Assertions:
- perp(b,e,d,e)

### D010 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(b,c,b,e,b,c,b,e)

### D011 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(e,b,c,c,e,b)

### D012 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,c)

### D013 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,d)

### D014 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(c,d)

### D015 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,e)

### D016 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(e,f)

### D017 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,f)

### D018 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(d,e)

### D019 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(d,g)

### D020 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(e,g)

### D021 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,f)

### D022 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,g)

### D023 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(f,g)

### D024 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(d,h)

### D025 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(e,h)

### D026 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(g,h)

### D027 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(b,c,e)

### D028 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,b,d)

### D029 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,b,e)

### D030 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,d,e)

### D031 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,b,f)

### D032 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(b,c,f)

### D033 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,e,f)

### D034 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(c,e,f)

### D035 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,b,g)

### D036 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,d,g)

### D037 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(b,d,g)

### D038 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,e,g)

### D039 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,d,h)

### D040 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,g,h)

### D041 `ar:ratio chasing:squared_distance`

Dependencies: D005

Assumptions:
- cong(b,c,b,e): (1/1)*|b-c|^2 + (-1/1)*|b-e|^2 = 0

Assertions:
- eqratio(b,c,b,e,b,e,b,c): (2/1)*|b-c|^2 + (-2/1)*|b-e|^2 = 0

### D042 `dd:r63`

Dependencies: D041, D010, D011

Assumptions:
- eqratio(b,c,b,e,b,e,b,c)
- eqangle(b,c,b,e,b,c,b,e)
- sameclock(e,b,c,c,e,b)

Assertions:
- simtrir(b,c,e,b,e,c)

### D043 `dd:r53`

Dependencies: D042, D011

Assumptions:
- simtrir(b,c,e,b,e,c)
- sameclock(e,b,c,c,e,b)

Assertions:
- eqangle(b,c,c,e,c,e,b,e)

### D044 `dd:r82`

Dependencies: D000, D012, D013, D014

Assumptions:
- coll(a,c,d)
- diff(a,c)
- diff(a,d)
- diff(c,d)

Assertions:
- para(a,c,c,d)

### D045 `dd:r82`

Dependencies: D000, D012, D013, D014

Assumptions:
- coll(a,c,d)
- diff(a,c)
- diff(a,d)
- diff(c,d)

Assertions:
- para(a,c,a,d)

### D046 `dd:r82`

Dependencies: D002, D015, D016, D017

Assumptions:
- coll(b,e,f)
- diff(b,e)
- diff(e,f)
- diff(b,f)

Assertions:
- para(b,e,b,f)

### D047 `dd:r82`

Dependencies: D002, D015, D016, D017

Assumptions:
- coll(b,e,f)
- diff(b,e)
- diff(e,f)
- diff(b,f)

Assertions:
- para(b,e,e,f)

### D048 `dd:r82`

Dependencies: D003, D018, D019, D020

Assumptions:
- coll(d,e,g)
- diff(d,e)
- diff(d,g)
- diff(e,g)

Assertions:
- para(d,e,e,g)

### D049 `dd:r82`

Dependencies: D003, D018, D019, D020

Assumptions:
- coll(d,e,g)
- diff(d,e)
- diff(d,g)
- diff(e,g)

Assertions:
- para(d,e,d,g)

### D050 `dd:r82`

Dependencies: D001, D021, D022, D023

Assumptions:
- coll(a,f,g)
- diff(a,f)
- diff(a,g)
- diff(f,g)

Assertions:
- para(a,f,f,g)

### D051 `dd:r82`

Dependencies: D001, D021, D022, D023

Assumptions:
- coll(a,f,g)
- diff(a,f)
- diff(a,g)
- diff(f,g)

Assertions:
- para(a,f,a,g)

### D052 `dd:r82`

Dependencies: D004, D018, D024, D025

Assumptions:
- coll(d,e,h)
- diff(d,e)
- diff(d,h)
- diff(e,h)

Assertions:
- para(d,e,d,h)

### D053 `ar:angle chasing:directed_angle`

Dependencies: D049, D052

Assumptions:
- para(d,e,d,g): (1/1)*∠(d-e) + (-1/1)*∠(d-g) = 0
- para(d,e,d,h): (1/1)*∠(d-e) + (-1/1)*∠(d-h) = 0

Assertions:
- para(d,g,d,h): (1/1)*∠(d-g) + (-1/1)*∠(d-h) = 0

### D054 `dd:r28`

Dependencies: D053

Assumptions:
- para(d,g,d,h)

Assertions:
- coll(d,g,h)

### D055 `dd:r82`

Dependencies: D054, D024, D026, D019

Assumptions:
- coll(d,g,h)
- diff(d,h)
- diff(g,h)
- diff(d,g)

Assertions:
- para(d,h,g,h)

### D056 `ar:angle chasing:directed_angle`

Dependencies: D048, D052, D055

Assumptions:
- para(d,e,e,g): (1/1)*∠(d-e) + (-1/1)*∠(e-g) = 0
- para(d,e,d,h): (1/1)*∠(d-e) + (-1/1)*∠(d-h) = 0
- para(d,h,g,h): (1/1)*∠(d-h) + (-1/1)*∠(g-h) = 0

Assertions:
- para(e,g,g,h): (1/1)*∠(e-g) + (-1/1)*∠(g-h) = 0

### D057 `dd:r28`

Dependencies: D056

Assumptions:
- para(e,g,g,h)

Assertions:
- coll(e,g,h)

### D058 `ar:angle chasing:directed_angle`

Dependencies: D006

Assumptions:
- para(a,h,b,g): (1/1)*∠(a-h) + (-1/1)*∠(b-g) = 0

Assertions:
- eqangle(a,g,b,g,a,g,a,h): (-1/1)*∠(a-h) + (1/1)*∠(b-g) = 0

### D059 `internal_theorem`

Dependencies: D058

Assumptions:
- eqangle(a,g,b,g,a,g,a,h)

Assertions:
- equation_class Yuclid::SinOrDist(a,g,b,g,a,h)

### D060 `ar:angle chasing:directed_angle`

Dependencies: D006, D048, D052

Assumptions:
- para(a,h,b,g): (1/1)*∠(a-h) + (-1/1)*∠(b-g) = 0
- para(d,e,e,g): (1/1)*∠(d-e) + (-1/1)*∠(e-g) = 0
- para(d,e,d,h): (1/1)*∠(d-e) + (-1/1)*∠(d-h) = 0

Assertions:
- eqangle(a,h,d,h,b,g,e,g): (-1/1)*∠(a-h) + (1/1)*∠(b-g) + (1/1)*∠(d-h) + (-1/1)*∠(e-g) = 0

### D061 `internal_theorem`

Dependencies: D060

Assumptions:
- eqangle(a,h,d,h,b,g,e,g)

Assertions:
- equation_class Yuclid::SinOrDist(a,h,d,b,g,e)

### D062 `ar:angle chasing:directed_angle`

Dependencies: D048, D049

Assumptions:
- para(d,e,e,g): (1/1)*∠(d-e) + (-1/1)*∠(e-g) = 0
- para(d,e,d,g): (1/1)*∠(d-e) + (-1/1)*∠(d-g) = 0

Assertions:
- eqangle(b,g,d,g,b,g,e,g): (1/1)*∠(d-g) + (-1/1)*∠(e-g) = 0

### D063 `internal_theorem`

Dependencies: D062

Assumptions:
- eqangle(b,g,d,g,b,g,e,g)

Assertions:
- equation_class Yuclid::SinOrDist(b,g,d,b,g,e)

### D064 `ar:angle chasing:directed_angle`

Dependencies: D049, D050, D051, D052, D055

Assumptions:
- para(d,e,d,g): (1/1)*∠(d-e) + (-1/1)*∠(d-g) = 0
- para(a,f,f,g): (1/1)*∠(a-f) + (-1/1)*∠(f-g) = 0
- para(a,f,a,g): (1/1)*∠(a-f) + (-1/1)*∠(a-g) = 0
- para(d,e,d,h): (1/1)*∠(d-e) + (-1/1)*∠(d-h) = 0
- para(d,h,g,h): (1/1)*∠(d-h) + (-1/1)*∠(g-h) = 0

Assertions:
- eqangle(a,g,d,g,f,g,g,h): (-1/1)*∠(a-g) + (1/1)*∠(d-g) + (1/1)*∠(f-g) + (-1/1)*∠(g-h) = 0

### D065 `internal_theorem`

Dependencies: D064

Assumptions:
- eqangle(a,g,d,g,f,g,g,h)

Assertions:
- equation_class Yuclid::SinOrDist(a,g,d,f,g,h)

### D066 `ar:angle chasing:directed_angle`

Dependencies: D050, D051

Assumptions:
- para(a,f,f,g): (1/1)*∠(a-f) + (-1/1)*∠(f-g) = 0
- para(a,f,a,g): (1/1)*∠(a-f) + (-1/1)*∠(a-g) = 0

Assertions:
- eqangle(a,g,g,h,f,g,g,h): (-1/1)*∠(a-g) + (1/1)*∠(f-g) = 0

### D067 `internal_theorem`

Dependencies: D066

Assumptions:
- eqangle(a,g,g,h,f,g,g,h)

Assertions:
- equation_class Yuclid::SinOrDist(a,g,h,f,g,h)

### D068 `ar:angle chasing:directed_angle`

Dependencies: D051

Assumptions:
- para(a,f,a,g): (1/1)*∠(a-f) + (-1/1)*∠(a-g) = 0

Assertions:
- eqangle(a,b,a,f,a,b,a,g): (1/1)*∠(a-f) + (-1/1)*∠(a-g) = 0

### D069 `internal_theorem`

Dependencies: D068

Assumptions:
- eqangle(a,b,a,f,a,b,a,g)

Assertions:
- equation_class Yuclid::SinOrDist(b,a,f,b,a,g)

### D070 `ar:angle chasing:directed_angle`

Dependencies: D045

Assumptions:
- para(a,c,a,d): (1/1)*∠(a-c) + (-1/1)*∠(a-d) = 0

Assertions:
- eqangle(a,b,a,c,a,b,a,d): (1/1)*∠(a-c) + (-1/1)*∠(a-d) = 0

### D071 `internal_theorem`

Dependencies: D070

Assumptions:
- eqangle(a,b,a,c,a,b,a,d)

Assertions:
- equation_class Yuclid::SinOrDist(b,a,c,b,a,d)

### D072 `ar:angle chasing:directed_angle`

Dependencies: D007, D008

Assumptions:
- perp(a,b,c,f): (1/1)*∠(a-b) + (-1/1)*∠(c-f) = 0
- perp(a,c,b,c): (1/1)*∠(a-c) + (-1/1)*∠(b-c) = 0

Assertions:
- eqangle(a,b,a,c,c,f,b,c): (-1/1)*∠(a-b) + (1/1)*∠(a-c) + (-1/1)*∠(b-c) + (1/1)*∠(c-f) = 0

### D073 `internal_theorem`

Dependencies: D072

Assumptions:
- eqangle(a,b,a,c,c,f,b,c)

Assertions:
- equation_class Yuclid::SinOrDist(b,a,c,b,c,f)

### D074 `ar:angle chasing:directed_angle`

Dependencies: D008, D009, D044

Assumptions:
- perp(a,c,b,c): (1/1)*∠(a-c) + (-1/1)*∠(b-c) = 0
- perp(b,e,d,e): (1/1)*∠(b-e) + (-1/1)*∠(d-e) = 0
- para(a,c,c,d): (1/1)*∠(a-c) + (-1/1)*∠(c-d) = 0

Assertions:
- eqangle(b,c,b,e,c,d,d,e): (-1/1)*∠(b-c) + (1/1)*∠(b-e) + (1/1)*∠(c-d) + (-1/1)*∠(d-e) = 0

### D075 `dd:r04`

Dependencies: D074, D027

Assumptions:
- eqangle(b,c,b,e,c,d,d,e)
- ncoll(b,c,e)

Assertions:
- cyclic(b,c,d,e)

### D076 `dd:r03`

Dependencies: D075

Assumptions:
- cyclic(b,c,d,e)

Assertions:
- eqangle(b,d,b,e,c,d,c,e)

### D077 `ar:angle chasing:directed_angle`

Dependencies: D047

Assumptions:
- para(b,e,e,f): (1/1)*∠(b-e) + (-1/1)*∠(e-f) = 0

Assertions:
- eqangle(a,e,b,e,a,e,e,f): (1/1)*∠(b-e) + (-1/1)*∠(e-f) = 0

### D078 `internal_theorem`

Dependencies: D077

Assumptions:
- eqangle(a,e,b,e,a,e,e,f)

Assertions:
- equation_class Yuclid::SinOrDist(a,e,b,a,e,f)

### D079 `ar:angle chasing:directed_angle`

Dependencies: D051

Assumptions:
- para(a,f,a,g): (1/1)*∠(a-f) + (-1/1)*∠(a-g) = 0

Assertions:
- eqangle(a,e,a,f,a,e,a,g): (1/1)*∠(a-f) + (-1/1)*∠(a-g) = 0

### D080 `internal_theorem`

Dependencies: D079

Assumptions:
- eqangle(a,e,a,f,a,e,a,g)

Assertions:
- equation_class Yuclid::SinOrDist(e,a,f,e,a,g)

### D081 `ar:angle chasing:directed_angle`

Dependencies: D046

Assumptions:
- para(b,e,b,f): (1/1)*∠(b-e) + (-1/1)*∠(b-f) = 0

Assertions:
- eqangle(a,b,b,e,a,b,b,f): (1/1)*∠(b-e) + (-1/1)*∠(b-f) = 0

### D082 `internal_theorem`

Dependencies: D081

Assumptions:
- eqangle(a,b,b,e,a,b,b,f)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,e,a,b,f)

### D083 `ar:angle chasing:directed_angle`

Dependencies: D048

Assumptions:
- para(d,e,e,g): (1/1)*∠(d-e) + (-1/1)*∠(e-g) = 0

Assertions:
- eqangle(a,e,d,e,a,e,e,g): (1/1)*∠(d-e) + (-1/1)*∠(e-g) = 0

### D084 `internal_theorem`

Dependencies: D083

Assumptions:
- eqangle(a,e,d,e,a,e,e,g)

Assertions:
- equation_class Yuclid::SinOrDist(a,e,d,a,e,g)

### D085 `ar:angle chasing:directed_angle`

Dependencies: D043, D047

Assumptions:
- eqangle(b,c,c,e,c,e,b,e): (-1/1)*∠(b-c) + (-1/1)*∠(b-e) + (2/1)*∠(c-e) = 0
- para(b,e,e,f): (1/1)*∠(b-e) + (-1/1)*∠(e-f) = 0

Assertions:
- eqangle(b,c,c,e,c,e,e,f): (-1/1)*∠(b-c) + (2/1)*∠(c-e) + (-1/1)*∠(e-f) = 0

### D086 `internal_theorem`

Dependencies: D085

Assumptions:
- eqangle(b,c,c,e,c,e,e,f)

Assertions:
- equation_class Yuclid::SinOrDist(b,c,e,c,e,f)

### D087 `ar:angle chasing:directed_angle`

Dependencies: D008, D009, D044, D049, D076

Assumptions:
- perp(a,c,b,c): (1/1)*∠(a-c) + (-1/1)*∠(b-c) = 0
- perp(b,e,d,e): (1/1)*∠(b-e) + (-1/1)*∠(d-e) = 0
- para(a,c,c,d): (1/1)*∠(a-c) + (-1/1)*∠(c-d) = 0
- para(d,e,d,g): (1/1)*∠(d-e) + (-1/1)*∠(d-g) = 0
- eqangle(b,d,b,e,c,d,c,e): (-1/1)*∠(b-d) + (1/1)*∠(b-e) + (1/1)*∠(c-d) + (-1/1)*∠(c-e) = 0

Assertions:
- eqangle(b,c,c,e,b,d,d,g): (-1/1)*∠(b-c) + (1/1)*∠(b-d) + (1/1)*∠(c-e) + (-1/1)*∠(d-g) = 0

### D088 `internal_theorem`

Dependencies: D087

Assumptions:
- eqangle(b,c,c,e,b,d,d,g)

Assertions:
- equation_class Yuclid::SinOrDist(b,c,e,b,d,g)

### D089 `ar:angle chasing:directed_angle`

Dependencies: D049, D052

Assumptions:
- para(d,e,d,g): (1/1)*∠(d-e) + (-1/1)*∠(d-g) = 0
- para(d,e,d,h): (1/1)*∠(d-e) + (-1/1)*∠(d-h) = 0

Assertions:
- eqangle(a,d,d,g,a,d,d,h): (1/1)*∠(d-g) + (-1/1)*∠(d-h) = 0

### D090 `internal_theorem`

Dependencies: D089

Assumptions:
- eqangle(a,d,d,g,a,d,d,h)

Assertions:
- equation_class Yuclid::SinOrDist(a,d,g,a,d,h)

### D091 `ar:angle chasing:directed_angle`

Dependencies: D049

Assumptions:
- para(d,e,d,g): (1/1)*∠(d-e) + (-1/1)*∠(d-g) = 0

Assertions:
- eqangle(a,d,d,e,a,d,d,g): (1/1)*∠(d-e) + (-1/1)*∠(d-g) = 0

### D092 `internal_theorem`

Dependencies: D091

Assumptions:
- eqangle(a,d,d,e,a,d,d,g)

Assertions:
- equation_class Yuclid::SinOrDist(a,d,e,a,d,g)

### D093 `ar:angle chasing:directed_angle`

Dependencies: D008, D009, D045, D046, D049

Assumptions:
- perp(a,c,b,c): (1/1)*∠(a-c) + (-1/1)*∠(b-c) = 0
- perp(b,e,d,e): (1/1)*∠(b-e) + (-1/1)*∠(d-e) = 0
- para(a,c,a,d): (1/1)*∠(a-c) + (-1/1)*∠(a-d) = 0
- para(b,e,b,f): (1/1)*∠(b-e) + (-1/1)*∠(b-f) = 0
- para(d,e,d,g): (1/1)*∠(d-e) + (-1/1)*∠(d-g) = 0

Assertions:
- eqangle(a,d,d,g,b,c,b,f): (-1/1)*∠(a-d) + (1/1)*∠(b-c) + (-1/1)*∠(b-f) + (1/1)*∠(d-g) = 0

### D094 `internal_theorem`

Dependencies: D093

Assumptions:
- eqangle(a,d,d,g,b,c,b,f)

Assertions:
- equation_class Yuclid::SinOrDist(a,d,g,c,b,f)

### D095 `ar:angle chasing:directed_angle`

Dependencies: D007, D008, D043, D044, D076

Assumptions:
- perp(a,b,c,f): (1/1)*∠(a-b) + (-1/1)*∠(c-f) = 0
- perp(a,c,b,c): (1/1)*∠(a-c) + (-1/1)*∠(b-c) = 0
- eqangle(b,c,c,e,c,e,b,e): (-1/1)*∠(b-c) + (-1/1)*∠(b-e) + (2/1)*∠(c-e) = 0
- para(a,c,c,d): (1/1)*∠(a-c) + (-1/1)*∠(c-d) = 0
- eqangle(b,d,b,e,c,d,c,e): (-1/1)*∠(b-d) + (1/1)*∠(b-e) + (1/1)*∠(c-d) + (-1/1)*∠(c-e) = 0

Assertions:
- eqangle(a,b,b,d,c,f,c,e): (-1/1)*∠(a-b) + (1/1)*∠(b-d) + (-1/1)*∠(c-e) + (1/1)*∠(c-f) = 0

### D096 `internal_theorem`

Dependencies: D095

Assumptions:
- eqangle(a,b,b,d,c,f,c,e)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,d,e,c,f)

### D097 `internal_theorem`

Dependencies: D028

Assumptions:
- ncoll(a,b,d)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,d,b,a,d,a,d,b,d)

### D098 `internal_theorem`

Dependencies: D029

Assumptions:
- ncoll(a,b,e)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,e,a,e,b,a,b,a,e)

### D099 `internal_theorem`

Dependencies: D030

Assumptions:
- ncoll(a,d,e)

Assertions:
- equation_class Yuclid::SinOrDist(a,d,e,a,e,d,a,d,a,e)

### D100 `internal_theorem`

Dependencies: D031

Assumptions:
- ncoll(a,b,f)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,f,b,a,f,a,f,b,f)

### D101 `internal_theorem`

Dependencies: D032

Assumptions:
- ncoll(b,c,f)

Assertions:
- equation_class Yuclid::SinOrDist(b,c,f,c,b,f,b,f,c,f)

### D102 `internal_theorem`

Dependencies: D033

Assumptions:
- ncoll(a,e,f)

Assertions:
- equation_class Yuclid::SinOrDist(a,e,f,e,a,f,a,f,e,f)

### D103 `internal_theorem`

Dependencies: D034

Assumptions:
- ncoll(c,e,f)

Assertions:
- equation_class Yuclid::SinOrDist(c,e,f,e,c,f,c,f,e,f)

### D104 `internal_theorem`

Dependencies: D035

Assumptions:
- ncoll(a,b,g)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,g,b,a,g,a,g,b,g)

### D105 `internal_theorem`

Dependencies: D035

Assumptions:
- ncoll(a,b,g)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,g,a,g,b,a,b,a,g)

### D106 `internal_theorem`

Dependencies: D036

Assumptions:
- ncoll(a,d,g)

Assertions:
- equation_class Yuclid::SinOrDist(a,d,g,a,g,d,a,d,a,g)

### D107 `internal_theorem`

Dependencies: D037

Assumptions:
- ncoll(b,d,g)

Assertions:
- equation_class Yuclid::SinOrDist(b,d,g,b,g,d,b,d,b,g)

### D108 `internal_theorem`

Dependencies: D038

Assumptions:
- ncoll(a,e,g)

Assertions:
- equation_class Yuclid::SinOrDist(a,e,g,e,a,g,a,g,e,g)

### D109 `internal_theorem`

Dependencies: D039

Assumptions:
- ncoll(a,d,h)

Assertions:
- equation_class Yuclid::SinOrDist(a,d,h,a,h,d,a,d,a,h)

### D110 `internal_theorem`

Dependencies: D040

Assumptions:
- ncoll(a,g,h)

Assertions:
- equation_class Yuclid::SinOrDist(a,g,h,g,a,h,a,h,g,h)

### D111 `ar:ratio chasing:sine_squared+squared_distance` [SINE-DISTANCE BRIDGE]

Dependencies: D059, D061, D063, D065, D067, D069, D071, D073, D078, D080, D082, D084, D086, D088, D090, D092, D094, D096, D097, D098, D099, D100, D101, D102, D103, D104, D105, D106, D107, D108, D109, D110

Assumptions:
- equation_class Yuclid::SinOrDist(a,g,b,g,a,h): (1/1)*\sin² ∠(a g b) + (-1/1)*\sin² ∠(g a h) = 0
- equation_class Yuclid::SinOrDist(a,h,d,b,g,e): (1/1)*\sin² ∠(a h d) + (-1/1)*\sin² ∠(b g e) = 0
- equation_class Yuclid::SinOrDist(b,g,d,b,g,e): (1/1)*\sin² ∠(b g d) + (-1/1)*\sin² ∠(b g e) = 0
- equation_class Yuclid::SinOrDist(a,g,d,f,g,h): (1/1)*\sin² ∠(a g d) + (-1/1)*\sin² ∠(f g h) = 0
- equation_class Yuclid::SinOrDist(a,g,h,f,g,h): (1/1)*\sin² ∠(a g h) + (-1/1)*\sin² ∠(f g h) = 0
- equation_class Yuclid::SinOrDist(b,a,f,b,a,g): (1/1)*\sin² ∠(b a f) + (-1/1)*\sin² ∠(b a g) = 0
- equation_class Yuclid::SinOrDist(b,a,c,b,a,d): (1/1)*\sin² ∠(b a c) + (-1/1)*\sin² ∠(b a d) = 0
- equation_class Yuclid::SinOrDist(b,a,c,b,c,f): (1/1)*\sin² ∠(b a c) + (-1/1)*\sin² ∠(b c f) = 0
- equation_class Yuclid::SinOrDist(a,e,b,a,e,f): (1/1)*\sin² ∠(a e b) + (-1/1)*\sin² ∠(a e f) = 0
- equation_class Yuclid::SinOrDist(e,a,f,e,a,g): (1/1)*\sin² ∠(e a f) + (-1/1)*\sin² ∠(e a g) = 0
- equation_class Yuclid::SinOrDist(a,b,e,a,b,f): (1/1)*\sin² ∠(a b e) + (-1/1)*\sin² ∠(a b f) = 0
- equation_class Yuclid::SinOrDist(a,e,d,a,e,g): (1/1)*\sin² ∠(a e d) + (-1/1)*\sin² ∠(a e g) = 0
- equation_class Yuclid::SinOrDist(b,c,e,c,e,f): (1/1)*\sin² ∠(b c e) + (-1/1)*\sin² ∠(c e f) = 0
- equation_class Yuclid::SinOrDist(b,c,e,b,d,g): (1/1)*\sin² ∠(b c e) + (-1/1)*\sin² ∠(b d g) = 0
- equation_class Yuclid::SinOrDist(a,d,g,a,d,h): (1/1)*\sin² ∠(a d g) + (-1/1)*\sin² ∠(a d h) = 0
- equation_class Yuclid::SinOrDist(a,d,e,a,d,g): (1/1)*\sin² ∠(a d e) + (-1/1)*\sin² ∠(a d g) = 0
- equation_class Yuclid::SinOrDist(a,d,g,c,b,f): (1/1)*\sin² ∠(a d g) + (-1/1)*\sin² ∠(c b f) = 0
- equation_class Yuclid::SinOrDist(a,b,d,e,c,f): (1/1)*\sin² ∠(a b d) + (-1/1)*\sin² ∠(e c f) = 0
- equation_class Yuclid::SinOrDist(a,b,d,b,a,d,a,d,b,d): (1/1)*\sin² ∠(a b d) + (-1/1)*\sin² ∠(b a d) + (-1/1)*|a-d|^2 + (1/1)*|b-d|^2 = 0
- equation_class Yuclid::SinOrDist(a,b,e,a,e,b,a,b,a,e): (1/1)*\sin² ∠(a b e) + (-1/1)*\sin² ∠(a e b) + (1/1)*|a-b|^2 + (-1/1)*|a-e|^2 = 0
- equation_class Yuclid::SinOrDist(a,d,e,a,e,d,a,d,a,e): (1/1)*\sin² ∠(a d e) + (-1/1)*\sin² ∠(a e d) + (1/1)*|a-d|^2 + (-1/1)*|a-e|^2 = 0
- equation_class Yuclid::SinOrDist(a,b,f,b,a,f,a,f,b,f): (1/1)*\sin² ∠(a b f) + (-1/1)*\sin² ∠(b a f) + (-1/1)*|a-f|^2 + (1/1)*|b-f|^2 = 0
- equation_class Yuclid::SinOrDist(b,c,f,c,b,f,b,f,c,f): (1/1)*\sin² ∠(b c f) + (-1/1)*\sin² ∠(c b f) + (-1/1)*|b-f|^2 + (1/1)*|c-f|^2 = 0
- equation_class Yuclid::SinOrDist(a,e,f,e,a,f,a,f,e,f): (1/1)*\sin² ∠(a e f) + (-1/1)*\sin² ∠(e a f) + (-1/1)*|a-f|^2 + (1/1)*|e-f|^2 = 0
- equation_class Yuclid::SinOrDist(c,e,f,e,c,f,c,f,e,f): (1/1)*\sin² ∠(c e f) + (-1/1)*\sin² ∠(e c f) + (-1/1)*|c-f|^2 + (1/1)*|e-f|^2 = 0
- equation_class Yuclid::SinOrDist(a,b,g,b,a,g,a,g,b,g): (1/1)*\sin² ∠(a b g) + (-1/1)*\sin² ∠(b a g) + (-1/1)*|a-g|^2 + (1/1)*|b-g|^2 = 0
- equation_class Yuclid::SinOrDist(a,b,g,a,g,b,a,b,a,g): (1/1)*\sin² ∠(a b g) + (-1/1)*\sin² ∠(a g b) + (1/1)*|a-b|^2 + (-1/1)*|a-g|^2 = 0
- equation_class Yuclid::SinOrDist(a,d,g,a,g,d,a,d,a,g): (1/1)*\sin² ∠(a d g) + (-1/1)*\sin² ∠(a g d) + (1/1)*|a-d|^2 + (-1/1)*|a-g|^2 = 0
- equation_class Yuclid::SinOrDist(b,d,g,b,g,d,b,d,b,g): (1/1)*\sin² ∠(b d g) + (-1/1)*\sin² ∠(b g d) + (1/1)*|b-d|^2 + (-1/1)*|b-g|^2 = 0
- equation_class Yuclid::SinOrDist(a,e,g,e,a,g,a,g,e,g): (1/1)*\sin² ∠(a e g) + (-1/1)*\sin² ∠(e a g) + (-1/1)*|a-g|^2 + (1/1)*|e-g|^2 = 0
- equation_class Yuclid::SinOrDist(a,d,h,a,h,d,a,d,a,h): (1/1)*\sin² ∠(a d h) + (-1/1)*\sin² ∠(a h d) + (1/1)*|a-d|^2 + (-1/1)*|a-h|^2 = 0
- equation_class Yuclid::SinOrDist(a,g,h,g,a,h,a,h,g,h): (1/1)*\sin² ∠(a g h) + (-1/1)*\sin² ∠(g a h) + (-1/1)*|a-h|^2 + (1/1)*|g-h|^2 = 0

Assertions:
- cong(e,g,g,h): (1/1)*|e-g|^2 + (-1/1)*|g-h|^2 = 0

### D112 `dd:r54`

Dependencies: D057, D111

Assumptions:
- coll(e,g,h)
- cong(e,g,g,h)

Assertions:
- midp(g,e,h)
