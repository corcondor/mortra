# 2018IranGOMp3: Yuclid proof trace

- Certificate: `data/hageo-409-current-native-certified-rerun-2026-08-24-runs/proofs/2018IranGOMp3.json`
- Deductions read: 105
- Order: Yuclid certificate order; every deduction is retained.

## Complete deduction trace

### D000 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(a,c,x)

### D001 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(a,d,o2)

### D002 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(b,c,o1)

### D003 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(b,d,y)

### D004 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,o1,b,o1)

### D005 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,o1,d,o1)

### D006 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,o1,x,o1)

### D007 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,o2,b,o2)

### D008 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,o2,c,o2)

### D009 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,o2,y,o2)

### D010 `construction`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,b,b,o1,a,o1,a,b)

### D011 `construction`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,b,b,o2,a,o2,a,b)

### D012 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(a,d,o1,d,o1,a)

### D013 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,o1,d,o1,a,o1,d,o1)

### D014 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(d,o1,a,a,d,o1)

### D015 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(b,c,o2,c,o2,b)

### D016 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(b,o2,c,o2,b,o2,c,o2)

### D017 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(c,o2,b,b,c,o2)

### D018 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(b,x,o1,x,o1,b)

### D019 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(b,o1,x,o1,b,o1,x,o1)

### D020 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(x,o1,b,b,x,o1)

### D021 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(b,o2,y,o2,b,o2,y,o2)

### D022 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(b,o2,y,y,b,o2)

### D023 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,o1,x,o1,a,o1,x,o1)

### D024 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(a,o1,x,x,a,o1)

### D025 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(c,o2,y,o2,c,o2,y,o2)

### D026 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(c,o2,y,y,c,o2)

### D027 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(d,o1,x,o1,d,o1,x,o1)

### D028 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(d,o1,x,x,d,o1)

### D029 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,o2,c,o2,a,o2,c,o2)

### D030 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(c,o2,a,a,c,o2)

### D031 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(b,o1,d,o1,b,o1,d,o1)

### D032 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(d,o1,b,b,d,o1)

### D033 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,c)

### D034 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,x)

### D035 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(c,x)

### D036 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,d)

### D037 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,y)

### D038 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(d,y)

### D039 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,c)

### D040 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,o1)

### D041 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(c,o1)

### D042 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,d)

### D043 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,o2)

### D044 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(d,o2)

### D045 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,b,y)

### D046 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,d,x)

### D047 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,b,x)

### D048 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,c,y)

### D049 `ar:ratio chasing:squared_distance`

Dependencies: D005

Assumptions:
- cong(a,o1,d,o1): (1/1)*|a-o1|^2 + (-1/1)*|d-o1|^2 = 0

Assertions:
- eqratio(a,o1,d,o1,d,o1,a,o1): (2/1)*|a-o1|^2 + (-2/1)*|d-o1|^2 = 0

### D050 `dd:r63`

Dependencies: D049, D013, D014

Assumptions:
- eqratio(a,o1,d,o1,d,o1,a,o1)
- eqangle(a,o1,d,o1,a,o1,d,o1)
- sameclock(d,o1,a,a,d,o1)

Assertions:
- simtrir(a,d,o1,d,a,o1)

### D051 `dd:r53`

Dependencies: D050, D012

Assumptions:
- simtrir(a,d,o1,d,a,o1)
- sameclock(a,d,o1,d,o1,a)

Assertions:
- eqangle(a,d,d,o1,a,o1,a,d)

### D052 `ar:ratio chasing:squared_distance`

Dependencies: D007, D008

Assumptions:
- cong(a,o2,b,o2): (1/1)*|a-o2|^2 + (-1/1)*|b-o2|^2 = 0
- cong(a,o2,c,o2): (1/1)*|a-o2|^2 + (-1/1)*|c-o2|^2 = 0

Assertions:
- eqratio(b,o2,c,o2,c,o2,b,o2): (2/1)*|b-o2|^2 + (-2/1)*|c-o2|^2 = 0

### D053 `dd:r63`

Dependencies: D052, D016, D017

Assumptions:
- eqratio(b,o2,c,o2,c,o2,b,o2)
- eqangle(b,o2,c,o2,b,o2,c,o2)
- sameclock(c,o2,b,b,c,o2)

Assertions:
- simtrir(b,c,o2,c,b,o2)

### D054 `dd:r53`

Dependencies: D053, D015

Assumptions:
- simtrir(b,c,o2,c,b,o2)
- sameclock(b,c,o2,c,o2,b)

Assertions:
- eqangle(b,c,c,o2,b,o2,b,c)

### D055 `ar:ratio chasing:squared_distance`

Dependencies: D004, D006

Assumptions:
- cong(a,o1,b,o1): (1/1)*|a-o1|^2 + (-1/1)*|b-o1|^2 = 0
- cong(a,o1,x,o1): (1/1)*|a-o1|^2 + (-1/1)*|x-o1|^2 = 0

Assertions:
- eqratio(b,o1,x,o1,x,o1,b,o1): (2/1)*|b-o1|^2 + (-2/1)*|x-o1|^2 = 0

### D056 `dd:r63`

Dependencies: D055, D019, D020

Assumptions:
- eqratio(b,o1,x,o1,x,o1,b,o1)
- eqangle(b,o1,x,o1,b,o1,x,o1)
- sameclock(x,o1,b,b,x,o1)

Assertions:
- simtrir(b,x,o1,x,b,o1)

### D057 `dd:r53`

Dependencies: D056, D018

Assumptions:
- simtrir(b,x,o1,x,b,o1)
- sameclock(b,x,o1,x,o1,b)

Assertions:
- eqangle(b,x,x,o1,b,o1,b,x)

### D058 `ar:ratio chasing:squared_distance`

Dependencies: D007, D009

Assumptions:
- cong(a,o2,b,o2): (1/1)*|a-o2|^2 + (-1/1)*|b-o2|^2 = 0
- cong(a,o2,y,o2): (1/1)*|a-o2|^2 + (-1/1)*|y-o2|^2 = 0

Assertions:
- eqratio(b,o2,y,o2,y,o2,b,o2): (2/1)*|b-o2|^2 + (-2/1)*|y-o2|^2 = 0

### D059 `dd:r63`

Dependencies: D058, D021, D022

Assumptions:
- eqratio(b,o2,y,o2,y,o2,b,o2)
- eqangle(b,o2,y,o2,b,o2,y,o2)
- sameclock(b,o2,y,y,b,o2)

Assertions:
- simtrir(b,y,o2,y,b,o2)

### D060 `dd:r53`

Dependencies: D059, D022

Assumptions:
- simtrir(b,y,o2,y,b,o2)
- sameclock(b,o2,y,y,b,o2)

Assertions:
- eqangle(b,y,y,o2,b,o2,b,y)

### D061 `ar:ratio chasing:squared_distance`

Dependencies: D006

Assumptions:
- cong(a,o1,x,o1): (1/1)*|a-o1|^2 + (-1/1)*|x-o1|^2 = 0

Assertions:
- eqratio(a,o1,x,o1,x,o1,a,o1): (2/1)*|a-o1|^2 + (-2/1)*|x-o1|^2 = 0

### D062 `dd:r63`

Dependencies: D061, D023, D024

Assumptions:
- eqratio(a,o1,x,o1,x,o1,a,o1)
- eqangle(a,o1,x,o1,a,o1,x,o1)
- sameclock(a,o1,x,x,a,o1)

Assertions:
- simtrir(a,x,o1,x,a,o1)

### D063 `dd:r53`

Dependencies: D062, D024

Assumptions:
- simtrir(a,x,o1,x,a,o1)
- sameclock(a,o1,x,x,a,o1)

Assertions:
- eqangle(a,x,x,o1,a,o1,a,x)

### D064 `ar:ratio chasing:squared_distance`

Dependencies: D008, D009

Assumptions:
- cong(a,o2,c,o2): (1/1)*|a-o2|^2 + (-1/1)*|c-o2|^2 = 0
- cong(a,o2,y,o2): (1/1)*|a-o2|^2 + (-1/1)*|y-o2|^2 = 0

Assertions:
- eqratio(c,o2,y,o2,y,o2,c,o2): (2/1)*|c-o2|^2 + (-2/1)*|y-o2|^2 = 0

### D065 `dd:r63`

Dependencies: D064, D025, D026

Assumptions:
- eqratio(c,o2,y,o2,y,o2,c,o2)
- eqangle(c,o2,y,o2,c,o2,y,o2)
- sameclock(c,o2,y,y,c,o2)

Assertions:
- simtrir(c,y,o2,y,c,o2)

### D066 `dd:r53`

Dependencies: D065, D026

Assumptions:
- simtrir(c,y,o2,y,c,o2)
- sameclock(c,o2,y,y,c,o2)

Assertions:
- eqangle(c,y,y,o2,c,o2,c,y)

### D067 `ar:ratio chasing:squared_distance`

Dependencies: D005, D006

Assumptions:
- cong(a,o1,d,o1): (1/1)*|a-o1|^2 + (-1/1)*|d-o1|^2 = 0
- cong(a,o1,x,o1): (1/1)*|a-o1|^2 + (-1/1)*|x-o1|^2 = 0

Assertions:
- eqratio(d,o1,x,o1,x,o1,d,o1): (2/1)*|d-o1|^2 + (-2/1)*|x-o1|^2 = 0

### D068 `dd:r63`

Dependencies: D067, D027, D028

Assumptions:
- eqratio(d,o1,x,o1,x,o1,d,o1)
- eqangle(d,o1,x,o1,d,o1,x,o1)
- sameclock(d,o1,x,x,d,o1)

Assertions:
- simtrir(d,x,o1,x,d,o1)

### D069 `dd:r53`

Dependencies: D068, D028

Assumptions:
- simtrir(d,x,o1,x,d,o1)
- sameclock(d,o1,x,x,d,o1)

Assertions:
- eqangle(d,x,x,o1,d,o1,d,x)

### D070 `ar:ratio chasing:squared_distance`

Dependencies: D008

Assumptions:
- cong(a,o2,c,o2): (1/1)*|a-o2|^2 + (-1/1)*|c-o2|^2 = 0

Assertions:
- eqratio(a,o2,c,o2,c,o2,a,o2): (2/1)*|a-o2|^2 + (-2/1)*|c-o2|^2 = 0

### D071 `dd:r63`

Dependencies: D070, D029, D030

Assumptions:
- eqratio(a,o2,c,o2,c,o2,a,o2)
- eqangle(a,o2,c,o2,a,o2,c,o2)
- sameclock(c,o2,a,a,c,o2)

Assertions:
- simtrir(a,c,o2,c,a,o2)

### D072 `dd:r53`

Dependencies: D071, D030

Assumptions:
- simtrir(a,c,o2,c,a,o2)
- sameclock(c,o2,a,a,c,o2)

Assertions:
- eqangle(a,c,c,o2,a,o2,a,c)

### D073 `ar:ratio chasing:squared_distance`

Dependencies: D004, D005

Assumptions:
- cong(a,o1,b,o1): (1/1)*|a-o1|^2 + (-1/1)*|b-o1|^2 = 0
- cong(a,o1,d,o1): (1/1)*|a-o1|^2 + (-1/1)*|d-o1|^2 = 0

Assertions:
- eqratio(b,o1,d,o1,d,o1,b,o1): (2/1)*|b-o1|^2 + (-2/1)*|d-o1|^2 = 0

### D074 `dd:r63`

Dependencies: D073, D031, D032

Assumptions:
- eqratio(b,o1,d,o1,d,o1,b,o1)
- eqangle(b,o1,d,o1,b,o1,d,o1)
- sameclock(d,o1,b,b,d,o1)

Assertions:
- simtrir(b,d,o1,d,b,o1)

### D075 `dd:r53`

Dependencies: D074, D032

Assumptions:
- simtrir(b,d,o1,d,b,o1)
- sameclock(d,o1,b,b,d,o1)

Assertions:
- eqangle(b,d,d,o1,b,o1,b,d)

### D076 `dd:r82`

Dependencies: D000, D033, D034, D035

Assumptions:
- coll(a,c,x)
- diff(a,c)
- diff(a,x)
- diff(c,x)

Assertions:
- para(a,c,c,x)

### D077 `dd:r82`

Dependencies: D000, D033, D034, D035

Assumptions:
- coll(a,c,x)
- diff(a,c)
- diff(a,x)
- diff(c,x)

Assertions:
- para(a,c,a,x)

### D078 `dd:r82`

Dependencies: D003, D036, D037, D038

Assumptions:
- coll(b,d,y)
- diff(b,d)
- diff(b,y)
- diff(d,y)

Assertions:
- para(b,d,d,y)

### D079 `dd:r82`

Dependencies: D003, D036, D037, D038

Assumptions:
- coll(b,d,y)
- diff(b,d)
- diff(b,y)
- diff(d,y)

Assertions:
- para(b,d,b,y)

### D080 `dd:r82`

Dependencies: D002, D039, D040, D041

Assumptions:
- coll(b,c,o1)
- diff(b,c)
- diff(b,o1)
- diff(c,o1)

Assertions:
- para(b,c,b,o1)

### D081 `dd:r82`

Dependencies: D001, D042, D043, D044

Assumptions:
- coll(a,d,o2)
- diff(a,d)
- diff(a,o2)
- diff(d,o2)

Assertions:
- para(a,d,a,o2)

### D082 `ar:angle chasing:directed_angle`

Dependencies: D010, D051, D054, D060, D066, D072, D075, D079, D080, D081

Assumptions:
- eqangle(a,b,b,o1,a,o1,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o1) + (1/1)*∠(b-o1) = 0
- eqangle(a,d,d,o1,a,o1,a,d): (-2/1)*∠(a-d) + (1/1)*∠(a-o1) + (1/1)*∠(d-o1) = 0
- eqangle(b,c,c,o2,b,o2,b,c): (-2/1)*∠(b-c) + (1/1)*∠(b-o2) + (1/1)*∠(c-o2) = 0
- eqangle(b,y,y,o2,b,o2,b,y): (-2/1)*∠(b-y) + (1/1)*∠(b-o2) + (1/1)*∠(y-o2) = 0
- eqangle(c,y,y,o2,c,o2,c,y): (-2/1)*∠(c-y) + (1/1)*∠(c-o2) + (1/1)*∠(y-o2) = 0
- eqangle(a,c,c,o2,a,o2,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-o2) + (1/1)*∠(c-o2) = 0
- eqangle(b,d,d,o1,b,o1,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-o1) + (1/1)*∠(d-o1) = 0
- para(b,d,b,y): (1/1)*∠(b-d) + (-1/1)*∠(b-y) = 0
- para(b,c,b,o1): (1/1)*∠(b-c) + (-1/1)*∠(b-o1) = 0
- para(a,d,a,o2): (1/1)*∠(a-d) + (-1/1)*∠(a-o2) = 0

Assertions:
- eqangle(a,c,c,y,a,b,a,c): (1/1)*∠(a-b) + (-2/1)*∠(a-c) + (1/1)*∠(c-y) = 0

### D083 `internal_theorem`

Dependencies: D082

Assumptions:
- eqangle(a,c,c,y,a,b,a,c)

Assertions:
- equation_class Yuclid::SinOrDist(a,c,y,b,a,c)

### D084 `ar:angle chasing:directed_angle`

Dependencies: D010, D011, D051, D054, D072, D075, D079, D080, D081

Assumptions:
- eqangle(a,b,b,o1,a,o1,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o1) + (1/1)*∠(b-o1) = 0
- eqangle(a,b,b,o2,a,o2,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o2) + (1/1)*∠(b-o2) = 0
- eqangle(a,d,d,o1,a,o1,a,d): (-2/1)*∠(a-d) + (1/1)*∠(a-o1) + (1/1)*∠(d-o1) = 0
- eqangle(b,c,c,o2,b,o2,b,c): (-2/1)*∠(b-c) + (1/1)*∠(b-o2) + (1/1)*∠(c-o2) = 0
- eqangle(a,c,c,o2,a,o2,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-o2) + (1/1)*∠(c-o2) = 0
- eqangle(b,d,d,o1,b,o1,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-o1) + (1/1)*∠(d-o1) = 0
- para(b,d,b,y): (1/1)*∠(b-d) + (-1/1)*∠(b-y) = 0
- para(b,c,b,o1): (1/1)*∠(b-c) + (-1/1)*∠(b-o1) = 0
- para(a,d,a,o2): (1/1)*∠(a-d) + (-1/1)*∠(a-o2) = 0

Assertions:
- eqangle(a,b,b,y,a,b,a,c): (-1/1)*∠(a-c) + (1/1)*∠(b-y) = 0

### D085 `internal_theorem`

Dependencies: D084

Assumptions:
- eqangle(a,b,b,y,a,b,a,c)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,y,b,a,c)

### D086 `ar:angle chasing:directed_angle`

Dependencies: D010, D011, D051, D054, D072, D075, D077, D080, D081

Assumptions:
- eqangle(a,b,b,o1,a,o1,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o1) + (1/1)*∠(b-o1) = 0
- eqangle(a,b,b,o2,a,o2,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o2) + (1/1)*∠(b-o2) = 0
- eqangle(a,d,d,o1,a,o1,a,d): (-2/1)*∠(a-d) + (1/1)*∠(a-o1) + (1/1)*∠(d-o1) = 0
- eqangle(b,c,c,o2,b,o2,b,c): (-2/1)*∠(b-c) + (1/1)*∠(b-o2) + (1/1)*∠(c-o2) = 0
- eqangle(a,c,c,o2,a,o2,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-o2) + (1/1)*∠(c-o2) = 0
- eqangle(b,d,d,o1,b,o1,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-o1) + (1/1)*∠(d-o1) = 0
- para(a,c,a,x): (1/1)*∠(a-c) + (-1/1)*∠(a-x) = 0
- para(b,c,b,o1): (1/1)*∠(b-c) + (-1/1)*∠(b-o1) = 0
- para(a,d,a,o2): (1/1)*∠(a-d) + (-1/1)*∠(a-o2) = 0

Assertions:
- eqangle(a,x,b,x,b,d,b,x): (-1/1)*∠(a-x) + (1/1)*∠(b-d) = 0

### D087 `internal_theorem`

Dependencies: D086

Assumptions:
- eqangle(a,x,b,x,b,d,b,x)

Assertions:
- equation_class Yuclid::SinOrDist(a,x,b,d,b,x)

### D088 `ar:angle chasing:directed_angle`

Dependencies: D051, D057, D063, D075

Assumptions:
- eqangle(a,d,d,o1,a,o1,a,d): (-2/1)*∠(a-d) + (1/1)*∠(a-o1) + (1/1)*∠(d-o1) = 0
- eqangle(b,x,x,o1,b,o1,b,x): (-2/1)*∠(b-x) + (1/1)*∠(b-o1) + (1/1)*∠(x-o1) = 0
- eqangle(a,x,x,o1,a,o1,a,x): (-2/1)*∠(a-x) + (1/1)*∠(a-o1) + (1/1)*∠(x-o1) = 0
- eqangle(b,d,d,o1,b,o1,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-o1) + (1/1)*∠(d-o1) = 0

Assertions:
- eqangle(a,d,a,x,b,d,b,x): (-1/1)*∠(a-d) + (1/1)*∠(a-x) + (1/1)*∠(b-d) + (-1/1)*∠(b-x) = 0

### D089 `internal_theorem`

Dependencies: D088

Assumptions:
- eqangle(a,d,a,x,b,d,b,x)

Assertions:
- equation_class Yuclid::SinOrDist(d,a,x,d,b,x)

### D090 `ar:angle chasing:directed_angle`

Dependencies: D010, D011, D051, D054, D072, D075, D079, D080, D081

Assumptions:
- eqangle(a,b,b,o1,a,o1,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o1) + (1/1)*∠(b-o1) = 0
- eqangle(a,b,b,o2,a,o2,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o2) + (1/1)*∠(b-o2) = 0
- eqangle(a,d,d,o1,a,o1,a,d): (-2/1)*∠(a-d) + (1/1)*∠(a-o1) + (1/1)*∠(d-o1) = 0
- eqangle(b,c,c,o2,b,o2,b,c): (-2/1)*∠(b-c) + (1/1)*∠(b-o2) + (1/1)*∠(c-o2) = 0
- eqangle(a,c,c,o2,a,o2,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-o2) + (1/1)*∠(c-o2) = 0
- eqangle(b,d,d,o1,b,o1,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-o1) + (1/1)*∠(d-o1) = 0
- para(b,d,b,y): (1/1)*∠(b-d) + (-1/1)*∠(b-y) = 0
- para(b,c,b,o1): (1/1)*∠(b-c) + (-1/1)*∠(b-o1) = 0
- para(a,d,a,o2): (1/1)*∠(a-d) + (-1/1)*∠(a-o2) = 0

Assertions:
- eqangle(a,y,b,y,a,y,a,c): (-1/1)*∠(a-c) + (1/1)*∠(b-y) = 0

### D091 `internal_theorem`

Dependencies: D090

Assumptions:
- eqangle(a,y,b,y,a,y,a,c)

Assertions:
- equation_class Yuclid::SinOrDist(a,y,b,c,a,y)

### D092 `ar:angle chasing:directed_angle`

Dependencies: D010, D051, D057, D069

Assumptions:
- eqangle(a,b,b,o1,a,o1,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o1) + (1/1)*∠(b-o1) = 0
- eqangle(a,d,d,o1,a,o1,a,d): (-2/1)*∠(a-d) + (1/1)*∠(a-o1) + (1/1)*∠(d-o1) = 0
- eqangle(b,x,x,o1,b,o1,b,x): (-2/1)*∠(b-x) + (1/1)*∠(b-o1) + (1/1)*∠(x-o1) = 0
- eqangle(d,x,x,o1,d,o1,d,x): (-2/1)*∠(d-x) + (1/1)*∠(d-o1) + (1/1)*∠(x-o1) = 0

Assertions:
- eqangle(a,b,b,x,a,d,d,x): (-1/1)*∠(a-b) + (1/1)*∠(a-d) + (1/1)*∠(b-x) + (-1/1)*∠(d-x) = 0

### D093 `internal_theorem`

Dependencies: D092

Assumptions:
- eqangle(a,b,b,x,a,d,d,x)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,x,a,d,x)

### D094 `internal_theorem`

Dependencies: D047

Assumptions:
- ncoll(a,b,x)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,x,a,x,b,a,b,a,x)

### D095 `internal_theorem`

Dependencies: D046

Assumptions:
- ncoll(a,d,x)

Assertions:
- equation_class Yuclid::SinOrDist(a,d,x,d,a,x,a,x,d,x)

### D096 `internal_theorem`

Dependencies: D045

Assumptions:
- ncoll(a,b,y)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,y,a,y,b,a,b,a,y)

### D097 `internal_theorem`

Dependencies: D048

Assumptions:
- ncoll(a,c,y)

Assertions:
- equation_class Yuclid::SinOrDist(a,c,y,c,a,y,a,y,c,y)

### D098 `ar:angle chasing:directed_angle`

Dependencies: D010, D011, D060, D063, D066, D069, D072, D075, D077, D079

Assumptions:
- eqangle(a,b,b,o1,a,o1,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o1) + (1/1)*∠(b-o1) = 0
- eqangle(a,b,b,o2,a,o2,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o2) + (1/1)*∠(b-o2) = 0
- eqangle(b,y,y,o2,b,o2,b,y): (-2/1)*∠(b-y) + (1/1)*∠(b-o2) + (1/1)*∠(y-o2) = 0
- eqangle(a,x,x,o1,a,o1,a,x): (-2/1)*∠(a-x) + (1/1)*∠(a-o1) + (1/1)*∠(x-o1) = 0
- eqangle(c,y,y,o2,c,o2,c,y): (-2/1)*∠(c-y) + (1/1)*∠(c-o2) + (1/1)*∠(y-o2) = 0
- eqangle(d,x,x,o1,d,o1,d,x): (-2/1)*∠(d-x) + (1/1)*∠(d-o1) + (1/1)*∠(x-o1) = 0
- eqangle(a,c,c,o2,a,o2,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-o2) + (1/1)*∠(c-o2) = 0
- eqangle(b,d,d,o1,b,o1,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-o1) + (1/1)*∠(d-o1) = 0
- para(a,c,a,x): (1/1)*∠(a-c) + (-1/1)*∠(a-x) = 0
- para(b,d,b,y): (1/1)*∠(b-d) + (-1/1)*∠(b-y) = 0

Assertions:
- para(c,y,d,x): (1/1)*∠(c-y) + (-1/1)*∠(d-x) = 0

### D099 `ar:angle chasing:directed_angle`

Dependencies: D010, D011, D051, D054, D072, D075, D076, D078, D080, D081

Assumptions:
- eqangle(a,b,b,o1,a,o1,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o1) + (1/1)*∠(b-o1) = 0
- eqangle(a,b,b,o2,a,o2,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o2) + (1/1)*∠(b-o2) = 0
- eqangle(a,d,d,o1,a,o1,a,d): (-2/1)*∠(a-d) + (1/1)*∠(a-o1) + (1/1)*∠(d-o1) = 0
- eqangle(b,c,c,o2,b,o2,b,c): (-2/1)*∠(b-c) + (1/1)*∠(b-o2) + (1/1)*∠(c-o2) = 0
- eqangle(a,c,c,o2,a,o2,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-o2) + (1/1)*∠(c-o2) = 0
- eqangle(b,d,d,o1,b,o1,b,d): (-2/1)*∠(b-d) + (1/1)*∠(b-o1) + (1/1)*∠(d-o1) = 0
- para(a,c,c,x): (1/1)*∠(a-c) + (-1/1)*∠(c-x) = 0
- para(b,d,d,y): (1/1)*∠(b-d) + (-1/1)*∠(d-y) = 0
- para(b,c,b,o1): (1/1)*∠(b-c) + (-1/1)*∠(b-o1) = 0
- para(a,d,a,o2): (1/1)*∠(a-d) + (-1/1)*∠(a-o2) = 0

Assertions:
- para(c,x,d,y): (1/1)*∠(c-x) + (-1/1)*∠(d-y) = 0

### D100 `internal_theorem`

Dependencies: D098, D099

Assumptions:
- para(c,y,d,x)
- para(c,x,d,y)

Assertions:
- equation_class Yuclid::SquaredDist(c,d,c,y,d,y,x,y)

### D101 `internal_theorem`

Dependencies: D099, D098

Assumptions:
- para(c,x,d,y)
- para(c,y,d,x)

Assertions:
- equation_class Yuclid::SquaredDist(c,d,c,x,d,x,x,y)

### D102 `ar:ratio chasing:sine_squared+squared_distance` [SINE-DISTANCE BRIDGE]

Dependencies: D087, D089, D093, D094, D095

Assumptions:
- equation_class Yuclid::SinOrDist(a,x,b,d,b,x): (1/1)*\sin² ∠(a x b) + (-1/1)*\sin² ∠(d b x) = 0
- equation_class Yuclid::SinOrDist(d,a,x,d,b,x): (1/1)*\sin² ∠(d a x) + (-1/1)*\sin² ∠(d b x) = 0
- equation_class Yuclid::SinOrDist(a,b,x,a,d,x): (1/1)*\sin² ∠(a b x) + (-1/1)*\sin² ∠(a d x) = 0
- equation_class Yuclid::SinOrDist(a,b,x,a,x,b,a,b,a,x): (1/1)*\sin² ∠(a b x) + (-1/1)*\sin² ∠(a x b) + (1/1)*|a-b|^2 + (-1/1)*|a-x|^2 = 0
- equation_class Yuclid::SinOrDist(a,d,x,d,a,x,a,x,d,x): (1/1)*\sin² ∠(a d x) + (-1/1)*\sin² ∠(d a x) + (-1/1)*|a-x|^2 + (1/1)*|d-x|^2 = 0

Assertions:
- cong(a,b,d,x): (1/1)*|a-b|^2 + (-1/1)*|d-x|^2 = 0

### D103 `ar:ratio chasing:sine_squared+squared_distance` [SINE-DISTANCE BRIDGE]

Dependencies: D083, D085, D091, D096, D097

Assumptions:
- equation_class Yuclid::SinOrDist(a,c,y,b,a,c): (1/1)*\sin² ∠(a c y) + (-1/1)*\sin² ∠(b a c) = 0
- equation_class Yuclid::SinOrDist(a,b,y,b,a,c): (1/1)*\sin² ∠(a b y) + (-1/1)*\sin² ∠(b a c) = 0
- equation_class Yuclid::SinOrDist(a,y,b,c,a,y): (1/1)*\sin² ∠(a y b) + (-1/1)*\sin² ∠(c a y) = 0
- equation_class Yuclid::SinOrDist(a,b,y,a,y,b,a,b,a,y): (1/1)*\sin² ∠(a b y) + (-1/1)*\sin² ∠(a y b) + (1/1)*|a-b|^2 + (-1/1)*|a-y|^2 = 0
- equation_class Yuclid::SinOrDist(a,c,y,c,a,y,a,y,c,y): (1/1)*\sin² ∠(a c y) + (-1/1)*\sin² ∠(c a y) + (-1/1)*|a-y|^2 + (1/1)*|c-y|^2 = 0

Assertions:
- cong(a,b,c,y): (1/1)*|a-b|^2 + (-1/1)*|c-y|^2 = 0

### D104 `ar:squared lengths chasing:squared_distance`

Dependencies: D100, D101, D102, D103

Assumptions:
- equation_class Yuclid::SquaredDist(c,d,c,y,d,y,x,y): (1/1)*|c-d|^2 + (-2/1)*|c-y|^2 + (-2/1)*|d-y|^2 + (1/1)*|x-y|^2 = 0
- equation_class Yuclid::SquaredDist(c,d,c,x,d,x,x,y): (1/1)*|c-d|^2 + (-2/1)*|c-x|^2 + (-2/1)*|d-x|^2 + (1/1)*|x-y|^2 = 0
- cong(a,b,d,x): (1/1)*|a-b|^2 + (-1/1)*|d-x|^2 = 0
- cong(a,b,c,y): (1/1)*|a-b|^2 + (-1/1)*|c-y|^2 = 0

Assertions:
- cong(c,x,d,y): (1/1)*|c-x|^2 + (-1/1)*|d-y|^2 = 0
