# 2015IranGOAp1: Yuclid proof trace

- Certificate: `data/hageo-409-current-native-certified-rerun-2026-08-24-runs/proofs/2015IranGOAp1.json`
- Deductions read: 85
- Order: Yuclid certificate order; every deduction is retained.

## Complete deduction trace

### D000 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(k,y,x1)

### D001 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(x,o1,x1)

### D002 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,o1,b,o1)

### D003 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,o2,b,o2)

### D004 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,o2,x,o2)

### D005 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,o2,k,o2)

### D006 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,o1,y,o1)

### D007 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,o2,x1,o2)

### D008 `construction`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,b,b,o1,a,o1,a,b)

### D009 `construction`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,b,b,o2,a,o2,a,b)

### D010 `construction`

Dependencies: none

Assumptions: none

Assertions:
- perp(b,x,b,y)

### D011 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(k,x1,o2,x1,o2,k)

### D012 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(k,o2,x1,o2,k,o2,x1,o2)

### D013 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(x1,o2,k,k,x1,o2)

### D014 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(y,a,o1,a,o1,y)

### D015 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,o1,y,o1,a,o1,y,o1)

### D016 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(a,o1,y,y,a,o1)

### D017 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(k,o2,x,o2,k,o2,x,o2)

### D018 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(x,o2,k,k,x,o2)

### D019 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,o2,x,o2,a,o2,x,o2)

### D020 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(a,o2,x,x,a,o2)

### D021 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(x,o2,x1,o2,x,o2,x1,o2)

### D022 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(x,o2,x1,x1,x,o2)

### D023 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(b,o1,y,o1,b,o1,y,o1)

### D024 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(y,o1,b,b,y,o1)

### D025 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(b,o2,x,o2,b,o2,x,o2)

### D026 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(b,o2,x,x,b,o2)

### D027 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(a,k,o2,k,o2,a)

### D028 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,o2,k,o2,a,o2,k,o2)

### D029 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(k,o2,a,a,k,o2)

### D030 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(a,x1,o2,x1,o2,a)

### D031 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,o2,x1,o2,a,o2,x1,o2)

### D032 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(x1,o2,a,a,x1,o2)

### D033 `dd:by reflexivity`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(b,o2,k,o2,b,o2,k,o2)

### D034 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(b,o2,k,k,b,o2)

### D035 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(x,x1)

### D036 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(x,o1)

### D037 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(o1,x1)

### D038 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(k,y)

### D039 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(y,x1)

### D040 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(k,x1)

### D041 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,y,x1)

### D042 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,k,x)

### D043 `ar:ratio chasing:squared_distance`

Dependencies: D005, D007

Assumptions:
- cong(a,o2,k,o2): (1/1)*|a-o2|^2 + (-1/1)*|k-o2|^2 = 0
- cong(a,o2,x1,o2): (1/1)*|a-o2|^2 + (-1/1)*|x1-o2|^2 = 0

Assertions:
- eqratio(k,o2,x1,o2,x1,o2,k,o2): (2/1)*|k-o2|^2 + (-2/1)*|x1-o2|^2 = 0

### D044 `dd:r63`

Dependencies: D043, D012, D013

Assumptions:
- eqratio(k,o2,x1,o2,x1,o2,k,o2)
- eqangle(k,o2,x1,o2,k,o2,x1,o2)
- sameclock(x1,o2,k,k,x1,o2)

Assertions:
- simtrir(k,x1,o2,x1,k,o2)

### D045 `dd:r53`

Dependencies: D044, D011

Assumptions:
- simtrir(k,x1,o2,x1,k,o2)
- sameclock(k,x1,o2,x1,o2,k)

Assertions:
- eqangle(k,x1,x1,o2,k,o2,k,x1)

### D046 `ar:ratio chasing:squared_distance`

Dependencies: D006

Assumptions:
- cong(a,o1,y,o1): (1/1)*|a-o1|^2 + (-1/1)*|y-o1|^2 = 0

Assertions:
- eqratio(a,o1,y,o1,y,o1,a,o1): (2/1)*|a-o1|^2 + (-2/1)*|y-o1|^2 = 0

### D047 `dd:r63`

Dependencies: D046, D015, D016

Assumptions:
- eqratio(a,o1,y,o1,y,o1,a,o1)
- eqangle(a,o1,y,o1,a,o1,y,o1)
- sameclock(a,o1,y,y,a,o1)

Assertions:
- simtrir(a,y,o1,y,a,o1)

### D048 `dd:r53`

Dependencies: D047, D014

Assumptions:
- simtrir(a,y,o1,y,a,o1)
- sameclock(y,a,o1,a,o1,y)

Assertions:
- eqangle(a,y,y,o1,a,o1,a,y)

### D049 `ar:ratio chasing:squared_distance`

Dependencies: D004, D005

Assumptions:
- cong(a,o2,x,o2): (1/1)*|a-o2|^2 + (-1/1)*|x-o2|^2 = 0
- cong(a,o2,k,o2): (1/1)*|a-o2|^2 + (-1/1)*|k-o2|^2 = 0

Assertions:
- eqratio(k,o2,x,o2,x,o2,k,o2): (2/1)*|k-o2|^2 + (-2/1)*|x-o2|^2 = 0

### D050 `dd:r63`

Dependencies: D049, D017, D018

Assumptions:
- eqratio(k,o2,x,o2,x,o2,k,o2)
- eqangle(k,o2,x,o2,k,o2,x,o2)
- sameclock(x,o2,k,k,x,o2)

Assertions:
- simtrir(k,x,o2,x,k,o2)

### D051 `dd:r53`

Dependencies: D050, D018

Assumptions:
- simtrir(k,x,o2,x,k,o2)
- sameclock(x,o2,k,k,x,o2)

Assertions:
- eqangle(k,x,x,o2,k,o2,k,x)

### D052 `ar:ratio chasing:squared_distance`

Dependencies: D004

Assumptions:
- cong(a,o2,x,o2): (1/1)*|a-o2|^2 + (-1/1)*|x-o2|^2 = 0

Assertions:
- eqratio(a,o2,x,o2,x,o2,a,o2): (2/1)*|a-o2|^2 + (-2/1)*|x-o2|^2 = 0

### D053 `dd:r63`

Dependencies: D052, D019, D020

Assumptions:
- eqratio(a,o2,x,o2,x,o2,a,o2)
- eqangle(a,o2,x,o2,a,o2,x,o2)
- sameclock(a,o2,x,x,a,o2)

Assertions:
- simtrir(a,x,o2,x,a,o2)

### D054 `dd:r53`

Dependencies: D053, D020

Assumptions:
- simtrir(a,x,o2,x,a,o2)
- sameclock(a,o2,x,x,a,o2)

Assertions:
- eqangle(a,x,x,o2,a,o2,a,x)

### D055 `ar:ratio chasing:squared_distance`

Dependencies: D004, D007

Assumptions:
- cong(a,o2,x,o2): (1/1)*|a-o2|^2 + (-1/1)*|x-o2|^2 = 0
- cong(a,o2,x1,o2): (1/1)*|a-o2|^2 + (-1/1)*|x1-o2|^2 = 0

Assertions:
- eqratio(x,o2,x1,o2,x1,o2,x,o2): (2/1)*|x-o2|^2 + (-2/1)*|x1-o2|^2 = 0

### D056 `dd:r63`

Dependencies: D055, D021, D022

Assumptions:
- eqratio(x,o2,x1,o2,x1,o2,x,o2)
- eqangle(x,o2,x1,o2,x,o2,x1,o2)
- sameclock(x,o2,x1,x1,x,o2)

Assertions:
- simtrir(x,x1,o2,x1,x,o2)

### D057 `dd:r53`

Dependencies: D056, D022

Assumptions:
- simtrir(x,x1,o2,x1,x,o2)
- sameclock(x,o2,x1,x1,x,o2)

Assertions:
- eqangle(x,x1,x1,o2,x,o2,x,x1)

### D058 `ar:ratio chasing:squared_distance`

Dependencies: D002, D006

Assumptions:
- cong(a,o1,b,o1): (1/1)*|a-o1|^2 + (-1/1)*|b-o1|^2 = 0
- cong(a,o1,y,o1): (1/1)*|a-o1|^2 + (-1/1)*|y-o1|^2 = 0

Assertions:
- eqratio(b,o1,y,o1,y,o1,b,o1): (2/1)*|b-o1|^2 + (-2/1)*|y-o1|^2 = 0

### D059 `dd:r63`

Dependencies: D058, D023, D024

Assumptions:
- eqratio(b,o1,y,o1,y,o1,b,o1)
- eqangle(b,o1,y,o1,b,o1,y,o1)
- sameclock(y,o1,b,b,y,o1)

Assertions:
- simtrir(b,y,o1,y,b,o1)

### D060 `dd:r53`

Dependencies: D059, D024

Assumptions:
- simtrir(b,y,o1,y,b,o1)
- sameclock(y,o1,b,b,y,o1)

Assertions:
- eqangle(b,y,y,o1,b,o1,b,y)

### D061 `ar:ratio chasing:squared_distance`

Dependencies: D003, D004

Assumptions:
- cong(a,o2,b,o2): (1/1)*|a-o2|^2 + (-1/1)*|b-o2|^2 = 0
- cong(a,o2,x,o2): (1/1)*|a-o2|^2 + (-1/1)*|x-o2|^2 = 0

Assertions:
- eqratio(b,o2,x,o2,x,o2,b,o2): (2/1)*|b-o2|^2 + (-2/1)*|x-o2|^2 = 0

### D062 `dd:r63`

Dependencies: D061, D025, D026

Assumptions:
- eqratio(b,o2,x,o2,x,o2,b,o2)
- eqangle(b,o2,x,o2,b,o2,x,o2)
- sameclock(b,o2,x,x,b,o2)

Assertions:
- simtrir(b,x,o2,x,b,o2)

### D063 `dd:r53`

Dependencies: D062, D026

Assumptions:
- simtrir(b,x,o2,x,b,o2)
- sameclock(b,o2,x,x,b,o2)

Assertions:
- eqangle(b,x,x,o2,b,o2,b,x)

### D064 `ar:ratio chasing:squared_distance`

Dependencies: D005

Assumptions:
- cong(a,o2,k,o2): (1/1)*|a-o2|^2 + (-1/1)*|k-o2|^2 = 0

Assertions:
- eqratio(a,o2,k,o2,k,o2,a,o2): (2/1)*|a-o2|^2 + (-2/1)*|k-o2|^2 = 0

### D065 `dd:r63`

Dependencies: D064, D028, D029

Assumptions:
- eqratio(a,o2,k,o2,k,o2,a,o2)
- eqangle(a,o2,k,o2,a,o2,k,o2)
- sameclock(k,o2,a,a,k,o2)

Assertions:
- simtrir(a,k,o2,k,a,o2)

### D066 `dd:r53`

Dependencies: D065, D027

Assumptions:
- simtrir(a,k,o2,k,a,o2)
- sameclock(a,k,o2,k,o2,a)

Assertions:
- eqangle(a,k,k,o2,a,o2,a,k)

### D067 `ar:ratio chasing:squared_distance`

Dependencies: D007

Assumptions:
- cong(a,o2,x1,o2): (1/1)*|a-o2|^2 + (-1/1)*|x1-o2|^2 = 0

Assertions:
- eqratio(a,o2,x1,o2,x1,o2,a,o2): (2/1)*|a-o2|^2 + (-2/1)*|x1-o2|^2 = 0

### D068 `dd:r63`

Dependencies: D067, D031, D032

Assumptions:
- eqratio(a,o2,x1,o2,x1,o2,a,o2)
- eqangle(a,o2,x1,o2,a,o2,x1,o2)
- sameclock(x1,o2,a,a,x1,o2)

Assertions:
- simtrir(a,x1,o2,x1,a,o2)

### D069 `dd:r53`

Dependencies: D068, D030

Assumptions:
- simtrir(a,x1,o2,x1,a,o2)
- sameclock(a,x1,o2,x1,o2,a)

Assertions:
- eqangle(a,x1,x1,o2,a,o2,a,x1)

### D070 `ar:ratio chasing:squared_distance`

Dependencies: D003, D005

Assumptions:
- cong(a,o2,b,o2): (1/1)*|a-o2|^2 + (-1/1)*|b-o2|^2 = 0
- cong(a,o2,k,o2): (1/1)*|a-o2|^2 + (-1/1)*|k-o2|^2 = 0

Assertions:
- eqratio(b,o2,k,o2,k,o2,b,o2): (2/1)*|b-o2|^2 + (-2/1)*|k-o2|^2 = 0

### D071 `dd:r63`

Dependencies: D070, D033, D034

Assumptions:
- eqratio(b,o2,k,o2,k,o2,b,o2)
- eqangle(b,o2,k,o2,b,o2,k,o2)
- sameclock(b,o2,k,k,b,o2)

Assertions:
- simtrir(b,k,o2,k,b,o2)

### D072 `dd:r53`

Dependencies: D071, D034

Assumptions:
- simtrir(b,k,o2,k,b,o2)
- sameclock(b,o2,k,k,b,o2)

Assertions:
- eqangle(b,k,k,o2,b,o2,b,k)

### D073 `dd:r82`

Dependencies: D001, D035, D036, D037

Assumptions:
- coll(x,o1,x1)
- diff(x,x1)
- diff(x,o1)
- diff(o1,x1)

Assertions:
- para(x,x1,o1,x1)

### D074 `dd:r82`

Dependencies: D000, D038, D039, D040

Assumptions:
- coll(k,y,x1)
- diff(k,y)
- diff(y,x1)
- diff(k,x1)

Assertions:
- para(k,y,k,x1)

### D075 `dd:r82`

Dependencies: D000, D038, D039, D040

Assumptions:
- coll(k,y,x1)
- diff(k,y)
- diff(y,x1)
- diff(k,x1)

Assertions:
- para(k,y,y,x1)

### D076 `ar:angle chasing:directed_angle`

Dependencies: D008, D009, D010, D048, D057, D060, D063, D069, D073

Assumptions:
- eqangle(a,b,b,o1,a,o1,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o1) + (1/1)*∠(b-o1) = 0
- eqangle(a,b,b,o2,a,o2,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o2) + (1/1)*∠(b-o2) = 0
- perp(b,x,b,y): (1/1)*∠(b-x) + (-1/1)*∠(b-y) = 0
- eqangle(a,y,y,o1,a,o1,a,y): (-2/1)*∠(a-y) + (1/1)*∠(a-o1) + (1/1)*∠(y-o1) = 0
- eqangle(x,x1,x1,o2,x,o2,x,x1): (-2/1)*∠(x-x1) + (1/1)*∠(x-o2) + (1/1)*∠(x1-o2) = 0
- eqangle(b,y,y,o1,b,o1,b,y): (-2/1)*∠(b-y) + (1/1)*∠(b-o1) + (1/1)*∠(y-o1) = 0
- eqangle(b,x,x,o2,b,o2,b,x): (-2/1)*∠(b-x) + (1/1)*∠(b-o2) + (1/1)*∠(x-o2) = 0
- eqangle(a,x1,x1,o2,a,o2,a,x1): (-2/1)*∠(a-x1) + (1/1)*∠(a-o2) + (1/1)*∠(x1-o2) = 0
- para(x,x1,o1,x1): (1/1)*∠(x-x1) + (-1/1)*∠(o1-x1) = 0

Assertions:
- eqangle(a,y,a,x1,y,o1,o1,x1): (-1/1)*∠(a-y) + (1/1)*∠(a-x1) + (1/1)*∠(y-o1) + (-1/1)*∠(o1-x1) = 0

### D077 `dd:r04`

Dependencies: D076, D041

Assumptions:
- eqangle(a,y,a,x1,y,o1,o1,x1)
- ncoll(a,y,x1)

Assertions:
- cyclic(a,y,o1,x1)

### D078 `dd:r03`

Dependencies: D077

Assumptions:
- cyclic(a,y,o1,x1)

Assertions:
- eqangle(a,o1,a,x1,y,o1,y,x1)

### D079 `ar:angle chasing:directed_angle`

Dependencies: D008, D009, D010, D045, D051, D060, D063, D066, D069, D072, D074, D075, D078

Assumptions:
- eqangle(a,b,b,o1,a,o1,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o1) + (1/1)*∠(b-o1) = 0
- eqangle(a,b,b,o2,a,o2,a,b): (-2/1)*∠(a-b) + (1/1)*∠(a-o2) + (1/1)*∠(b-o2) = 0
- perp(b,x,b,y): (1/1)*∠(b-x) + (-1/1)*∠(b-y) = 0
- eqangle(k,x1,x1,o2,k,o2,k,x1): (-2/1)*∠(k-x1) + (1/1)*∠(k-o2) + (1/1)*∠(x1-o2) = 0
- eqangle(k,x,x,o2,k,o2,k,x): (-2/1)*∠(k-x) + (1/1)*∠(k-o2) + (1/1)*∠(x-o2) = 0
- eqangle(b,y,y,o1,b,o1,b,y): (-2/1)*∠(b-y) + (1/1)*∠(b-o1) + (1/1)*∠(y-o1) = 0
- eqangle(b,x,x,o2,b,o2,b,x): (-2/1)*∠(b-x) + (1/1)*∠(b-o2) + (1/1)*∠(x-o2) = 0
- eqangle(a,k,k,o2,a,o2,a,k): (-2/1)*∠(a-k) + (1/1)*∠(a-o2) + (1/1)*∠(k-o2) = 0
- eqangle(a,x1,x1,o2,a,o2,a,x1): (-2/1)*∠(a-x1) + (1/1)*∠(a-o2) + (1/1)*∠(x1-o2) = 0
- eqangle(b,k,k,o2,b,o2,b,k): (-2/1)*∠(b-k) + (1/1)*∠(b-o2) + (1/1)*∠(k-o2) = 0
- para(k,y,k,x1): (1/1)*∠(k-y) + (-1/1)*∠(k-x1) = 0
- para(k,y,y,x1): (1/1)*∠(k-y) + (-1/1)*∠(y-x1) = 0
- eqangle(a,o1,a,x1,y,o1,y,x1): (-1/1)*∠(a-o1) + (1/1)*∠(a-x1) + (1/1)*∠(y-o1) + (-1/1)*∠(y-x1) = 0

Assertions:
- eqangle(a,k,k,x,b,x,b,k): (-1/1)*∠(a-k) + (-1/1)*∠(b-k) + (1/1)*∠(b-x) + (1/1)*∠(k-x) = 0

### D080 `internal_theorem`

Dependencies: D079

Assumptions:
- eqangle(a,k,k,x,b,x,b,k)

Assertions:
- equation_class Yuclid::SinOrDist(a,k,x,k,b,x)

### D081 `ar:angle chasing:directed_angle`

Dependencies: D054, D063, D066, D072

Assumptions:
- eqangle(a,x,x,o2,a,o2,a,x): (-2/1)*∠(a-x) + (1/1)*∠(a-o2) + (1/1)*∠(x-o2) = 0
- eqangle(b,x,x,o2,b,o2,b,x): (-2/1)*∠(b-x) + (1/1)*∠(b-o2) + (1/1)*∠(x-o2) = 0
- eqangle(a,k,k,o2,a,o2,a,k): (-2/1)*∠(a-k) + (1/1)*∠(a-o2) + (1/1)*∠(k-o2) = 0
- eqangle(b,k,k,o2,b,o2,b,k): (-2/1)*∠(b-k) + (1/1)*∠(b-o2) + (1/1)*∠(k-o2) = 0

Assertions:
- eqangle(a,k,a,x,b,k,b,x): (-1/1)*∠(a-k) + (1/1)*∠(a-x) + (1/1)*∠(b-k) + (-1/1)*∠(b-x) = 0

### D082 `internal_theorem`

Dependencies: D081

Assumptions:
- eqangle(a,k,a,x,b,k,b,x)

Assertions:
- equation_class Yuclid::SinOrDist(k,a,x,k,b,x)

### D083 `internal_theorem`

Dependencies: D042

Assumptions:
- ncoll(a,k,x)

Assertions:
- equation_class Yuclid::SinOrDist(a,k,x,k,a,x,a,x,k,x)

### D084 `ar:ratio chasing:sine_squared+squared_distance` [SINE-DISTANCE BRIDGE]

Dependencies: D080, D082, D083

Assumptions:
- equation_class Yuclid::SinOrDist(a,k,x,k,b,x): (1/1)*\sin² ∠(a k x) + (-1/1)*\sin² ∠(k b x) = 0
- equation_class Yuclid::SinOrDist(k,a,x,k,b,x): (1/1)*\sin² ∠(k a x) + (-1/1)*\sin² ∠(k b x) = 0
- equation_class Yuclid::SinOrDist(a,k,x,k,a,x,a,x,k,x): (1/1)*\sin² ∠(a k x) + (-1/1)*\sin² ∠(k a x) + (-1/1)*|a-x|^2 + (1/1)*|k-x|^2 = 0

Assertions:
- cong(a,x,k,x): (1/1)*|a-x|^2 + (-1/1)*|k-x|^2 = 0
