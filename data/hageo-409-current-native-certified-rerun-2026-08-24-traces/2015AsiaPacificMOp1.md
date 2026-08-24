# 2015AsiaPacificMOp1: Yuclid proof trace

- Certificate: `data/hageo-409-current-native-certified-rerun-2026-08-24-runs/proofs/2015AsiaPacificMOp1.json`
- Deductions read: 75
- Order: Yuclid certificate order; every deduction is retained.

## Complete deduction trace

### D000 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(a,b,x)

### D001 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(a,c,y)

### D002 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(b,c,d)

### D003 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(d,v,z)

### D004 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(d,x,y)

### D005 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(w,y,z)

### D006 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cyclic(a,b,c,v)

### D007 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cyclic(a,b,c,w)

### D008 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cyclic(a,b,c,z)

### D009 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cyclic(b,d,x,z)

### D010 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,d)

### D011 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,c)

### D012 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(c,d)

### D013 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,y)

### D014 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,c)

### D015 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(c,y)

### D016 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,b)

### D017 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,x)

### D018 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,x)

### D019 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(d,x)

### D020 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(x,y)

### D021 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(d,y)

### D022 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(d,v)

### D023 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(v,z)

### D024 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(d,z)

### D025 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(w,y)

### D026 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(w,z)

### D027 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(y,z)

### D028 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,b,v)

### D029 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(d,y,z)

### D030 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(c,v,z)

### D031 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(v,w,z)

### D032 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(c,v,w)

### D033 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,v,w)

### D034 `dd:r82`

Dependencies: D002, D010, D011, D012

Assumptions:
- coll(b,c,d)
- diff(b,d)
- diff(b,c)
- diff(c,d)

Assertions:
- para(b,d,c,d)

### D035 `dd:r82`

Dependencies: D002, D010, D011, D012

Assumptions:
- coll(b,c,d)
- diff(b,d)
- diff(b,c)
- diff(c,d)

Assertions:
- para(b,c,b,d)

### D036 `dd:r82`

Dependencies: D001, D013, D014, D015

Assumptions:
- coll(a,c,y)
- diff(a,y)
- diff(a,c)
- diff(c,y)

Assertions:
- para(a,y,c,y)

### D037 `dd:r82`

Dependencies: D001, D013, D014, D015

Assumptions:
- coll(a,c,y)
- diff(a,y)
- diff(a,c)
- diff(c,y)

Assertions:
- para(a,c,a,y)

### D038 `dd:r82`

Dependencies: D000, D016, D017, D018

Assumptions:
- coll(a,b,x)
- diff(a,b)
- diff(a,x)
- diff(b,x)

Assertions:
- para(a,b,b,x)

### D039 `dd:r82`

Dependencies: D004, D019, D020, D021

Assumptions:
- coll(d,x,y)
- diff(d,x)
- diff(x,y)
- diff(d,y)

Assertions:
- para(d,x,d,y)

### D040 `dd:r82`

Dependencies: D003, D022, D023, D024

Assumptions:
- coll(d,v,z)
- diff(d,v)
- diff(v,z)
- diff(d,z)

Assertions:
- para(d,v,d,z)

### D041 `dd:r82`

Dependencies: D003, D022, D023, D024

Assumptions:
- coll(d,v,z)
- diff(d,v)
- diff(v,z)
- diff(d,z)

Assertions:
- para(d,v,v,z)

### D042 `dd:r82`

Dependencies: D005, D025, D026, D027

Assumptions:
- coll(w,y,z)
- diff(w,y)
- diff(w,z)
- diff(y,z)

Assertions:
- para(w,y,y,z)

### D043 `dd:r82`

Dependencies: D005, D025, D026, D027

Assumptions:
- coll(w,y,z)
- diff(w,y)
- diff(w,z)
- diff(y,z)

Assertions:
- para(w,y,w,z)

### D044 `dd:r03`

Dependencies: D007

Assumptions:
- cyclic(a,b,c,w)

Assertions:
- eqangle(a,c,a,w,b,c,b,w)

### D045 `dd:r03`

Dependencies: D007

Assumptions:
- cyclic(a,b,c,w)

Assertions:
- eqangle(a,b,b,w,a,c,c,w)

### D046 `dd:r03`

Dependencies: D006

Assumptions:
- cyclic(a,b,c,v)

Assertions:
- eqangle(a,c,a,v,b,c,b,v)

### D047 `dd:r03`

Dependencies: D006

Assumptions:
- cyclic(a,b,c,v)

Assertions:
- eqangle(a,b,a,v,b,c,c,v)

### D048 `dd:r03`

Dependencies: D009

Assumptions:
- cyclic(b,d,x,z)

Assertions:
- eqangle(b,x,b,z,d,x,d,z)

### D049 `ar:angle chasing:directed_angle`

Dependencies: D045, D046, D047

Assumptions:
- eqangle(a,b,b,w,a,c,c,w): (-1/1)*∠(a-b) + (1/1)*∠(a-c) + (1/1)*∠(b-w) + (-1/1)*∠(c-w) = 0
- eqangle(a,c,a,v,b,c,b,v): (-1/1)*∠(a-c) + (1/1)*∠(a-v) + (1/1)*∠(b-c) + (-1/1)*∠(b-v) = 0
- eqangle(a,b,a,v,b,c,c,v): (-1/1)*∠(a-b) + (1/1)*∠(a-v) + (1/1)*∠(b-c) + (-1/1)*∠(c-v) = 0

Assertions:
- eqangle(b,v,b,w,c,v,c,w): (-1/1)*∠(b-v) + (1/1)*∠(b-w) + (1/1)*∠(c-v) + (-1/1)*∠(c-w) = 0

### D050 `dd:r04`

Dependencies: D049, D032

Assumptions:
- eqangle(b,v,b,w,c,v,c,w)
- ncoll(c,v,w)

Assertions:
- cyclic(b,c,v,w)

### D051 `dd:r03`

Dependencies: D050

Assumptions:
- cyclic(b,c,v,w)

Assertions:
- eqangle(b,c,c,w,b,v,v,w)

### D052 `ar:angle chasing:directed_angle`

Dependencies: D044, D045, D047

Assumptions:
- eqangle(a,c,a,w,b,c,b,w): (-1/1)*∠(a-c) + (1/1)*∠(a-w) + (1/1)*∠(b-c) + (-1/1)*∠(b-w) = 0
- eqangle(a,b,b,w,a,c,c,w): (-1/1)*∠(a-b) + (1/1)*∠(a-c) + (1/1)*∠(b-w) + (-1/1)*∠(c-w) = 0
- eqangle(a,b,a,v,b,c,c,v): (-1/1)*∠(a-b) + (1/1)*∠(a-v) + (1/1)*∠(b-c) + (-1/1)*∠(c-v) = 0

Assertions:
- eqangle(a,v,a,w,c,v,c,w): (-1/1)*∠(a-v) + (1/1)*∠(a-w) + (1/1)*∠(c-v) + (-1/1)*∠(c-w) = 0

### D053 `internal_theorem`

Dependencies: D052

Assumptions:
- eqangle(a,v,a,w,c,v,c,w)

Assertions:
- equation_class Yuclid::SinOrDist(v,a,w,v,c,w)

### D054 `ar:angle chasing:directed_angle`

Dependencies: D034, D035, D036, D037, D046

Assumptions:
- para(b,d,c,d): (1/1)*∠(b-d) + (-1/1)*∠(c-d) = 0
- para(b,c,b,d): (1/1)*∠(b-c) + (-1/1)*∠(b-d) = 0
- para(a,y,c,y): (1/1)*∠(a-y) + (-1/1)*∠(c-y) = 0
- para(a,c,a,y): (1/1)*∠(a-c) + (-1/1)*∠(a-y) = 0
- eqangle(a,c,a,v,b,c,b,v): (-1/1)*∠(a-c) + (1/1)*∠(a-v) + (1/1)*∠(b-c) + (-1/1)*∠(b-v) = 0

Assertions:
- eqangle(a,v,b,v,c,y,c,d): (-1/1)*∠(a-v) + (1/1)*∠(b-v) + (-1/1)*∠(c-d) + (1/1)*∠(c-y) = 0

### D055 `internal_theorem`

Dependencies: D054

Assumptions:
- eqangle(a,v,b,v,c,y,c,d)

Assertions:
- equation_class Yuclid::SinOrDist(a,v,b,d,c,y)

### D056 `dd:r03`

Dependencies: D008

Assumptions:
- cyclic(a,b,c,z)

Assertions:
- eqangle(a,c,a,z,b,c,b,z)

### D057 `dd:r03`

Dependencies: D008

Assumptions:
- cyclic(a,b,c,z)

Assertions:
- eqangle(a,b,a,z,b,c,c,z)

### D058 `ar:angle chasing:directed_angle`

Dependencies: D044, D045, D051

Assumptions:
- eqangle(a,c,a,w,b,c,b,w): (-1/1)*∠(a-c) + (1/1)*∠(a-w) + (1/1)*∠(b-c) + (-1/1)*∠(b-w) = 0
- eqangle(a,b,b,w,a,c,c,w): (-1/1)*∠(a-b) + (1/1)*∠(a-c) + (1/1)*∠(b-w) + (-1/1)*∠(c-w) = 0
- eqangle(b,c,c,w,b,v,v,w): (-1/1)*∠(b-c) + (1/1)*∠(b-v) + (1/1)*∠(c-w) + (-1/1)*∠(v-w) = 0

Assertions:
- eqangle(a,b,b,v,a,w,v,w): (-1/1)*∠(a-b) + (1/1)*∠(a-w) + (1/1)*∠(b-v) + (-1/1)*∠(v-w) = 0

### D059 `internal_theorem`

Dependencies: D058

Assumptions:
- eqangle(a,b,b,v,a,w,v,w)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,v,a,w,v)

### D060 `internal_theorem`

Dependencies: D028

Assumptions:
- ncoll(a,b,v)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,v,a,v,b,a,b,a,v)

### D061 `internal_theorem`

Dependencies: D033

Assumptions:
- ncoll(a,v,w)

Assertions:
- equation_class Yuclid::SinOrDist(a,v,w,v,a,w,a,w,v,w)

### D062 `internal_theorem`

Dependencies: D033

Assumptions:
- ncoll(a,v,w)

Assertions:
- equation_class Yuclid::SinOrDist(a,v,w,a,w,v,a,v,a,w)

### D063 `ar:angle chasing:directed_angle`

Dependencies: D036, D037, D038, D039, D048, D056, D057

Assumptions:
- para(a,y,c,y): (1/1)*∠(a-y) + (-1/1)*∠(c-y) = 0
- para(a,c,a,y): (1/1)*∠(a-c) + (-1/1)*∠(a-y) = 0
- para(a,b,b,x): (1/1)*∠(a-b) + (-1/1)*∠(b-x) = 0
- para(d,x,d,y): (1/1)*∠(d-x) + (-1/1)*∠(d-y) = 0
- eqangle(b,x,b,z,d,x,d,z): (-1/1)*∠(b-x) + (1/1)*∠(b-z) + (1/1)*∠(d-x) + (-1/1)*∠(d-z) = 0
- eqangle(a,c,a,z,b,c,b,z): (-1/1)*∠(a-c) + (1/1)*∠(a-z) + (1/1)*∠(b-c) + (-1/1)*∠(b-z) = 0
- eqangle(a,b,a,z,b,c,c,z): (-1/1)*∠(a-b) + (1/1)*∠(a-z) + (1/1)*∠(b-c) + (-1/1)*∠(c-z) = 0

Assertions:
- eqangle(c,y,c,z,d,y,d,z): (-1/1)*∠(c-y) + (1/1)*∠(c-z) + (1/1)*∠(d-y) + (-1/1)*∠(d-z) = 0

### D064 `dd:r04`

Dependencies: D063, D029

Assumptions:
- eqangle(c,y,c,z,d,y,d,z)
- ncoll(d,y,z)

Assertions:
- cyclic(c,d,y,z)

### D065 `dd:r03`

Dependencies: D064

Assumptions:
- cyclic(c,d,y,z)

Assertions:
- eqangle(c,d,d,z,c,y,y,z)

### D066 `ar:angle chasing:directed_angle`

Dependencies: D047, D057

Assumptions:
- eqangle(a,b,a,v,b,c,c,v): (-1/1)*∠(a-b) + (1/1)*∠(a-v) + (1/1)*∠(b-c) + (-1/1)*∠(c-v) = 0
- eqangle(a,b,a,z,b,c,c,z): (-1/1)*∠(a-b) + (1/1)*∠(a-z) + (1/1)*∠(b-c) + (-1/1)*∠(c-z) = 0

Assertions:
- eqangle(a,v,a,z,c,v,c,z): (-1/1)*∠(a-v) + (1/1)*∠(a-z) + (1/1)*∠(c-v) + (-1/1)*∠(c-z) = 0

### D067 `dd:r04`

Dependencies: D066, D030

Assumptions:
- eqangle(a,v,a,z,c,v,c,z)
- ncoll(c,v,z)

Assertions:
- cyclic(a,c,v,z)

### D068 `dd:r03`

Dependencies: D067

Assumptions:
- cyclic(a,c,v,z)

Assertions:
- eqangle(a,c,c,z,a,v,v,z)

### D069 `ar:angle chasing:directed_angle`

Dependencies: D044, D045, D046, D051, D057, D068

Assumptions:
- eqangle(a,c,a,w,b,c,b,w): (-1/1)*∠(a-c) + (1/1)*∠(a-w) + (1/1)*∠(b-c) + (-1/1)*∠(b-w) = 0
- eqangle(a,b,b,w,a,c,c,w): (-1/1)*∠(a-b) + (1/1)*∠(a-c) + (1/1)*∠(b-w) + (-1/1)*∠(c-w) = 0
- eqangle(a,c,a,v,b,c,b,v): (-1/1)*∠(a-c) + (1/1)*∠(a-v) + (1/1)*∠(b-c) + (-1/1)*∠(b-v) = 0
- eqangle(b,c,c,w,b,v,v,w): (-1/1)*∠(b-c) + (1/1)*∠(b-v) + (1/1)*∠(c-w) + (-1/1)*∠(v-w) = 0
- eqangle(a,b,a,z,b,c,c,z): (-1/1)*∠(a-b) + (1/1)*∠(a-z) + (1/1)*∠(b-c) + (-1/1)*∠(c-z) = 0
- eqangle(a,c,c,z,a,v,v,z): (-1/1)*∠(a-c) + (1/1)*∠(a-v) + (1/1)*∠(c-z) + (-1/1)*∠(v-z) = 0

Assertions:
- eqangle(a,w,a,z,v,w,v,z): (-1/1)*∠(a-w) + (1/1)*∠(a-z) + (1/1)*∠(v-w) + (-1/1)*∠(v-z) = 0

### D070 `dd:r04`

Dependencies: D069, D031

Assumptions:
- eqangle(a,w,a,z,v,w,v,z)
- ncoll(v,w,z)

Assertions:
- cyclic(a,v,w,z)

### D071 `dd:r03`

Dependencies: D070

Assumptions:
- cyclic(a,v,w,z)

Assertions:
- eqangle(a,v,v,z,a,w,w,z)

### D072 `ar:angle chasing:directed_angle`

Dependencies: D040, D041, D042, D043, D044, D045, D047, D065, D071

Assumptions:
- para(d,v,d,z): (1/1)*∠(d-v) + (-1/1)*∠(d-z) = 0
- para(d,v,v,z): (1/1)*∠(d-v) + (-1/1)*∠(v-z) = 0
- para(w,y,y,z): (1/1)*∠(w-y) + (-1/1)*∠(y-z) = 0
- para(w,y,w,z): (1/1)*∠(w-y) + (-1/1)*∠(w-z) = 0
- eqangle(a,c,a,w,b,c,b,w): (-1/1)*∠(a-c) + (1/1)*∠(a-w) + (1/1)*∠(b-c) + (-1/1)*∠(b-w) = 0
- eqangle(a,b,b,w,a,c,c,w): (-1/1)*∠(a-b) + (1/1)*∠(a-c) + (1/1)*∠(b-w) + (-1/1)*∠(c-w) = 0
- eqangle(a,b,a,v,b,c,c,v): (-1/1)*∠(a-b) + (1/1)*∠(a-v) + (1/1)*∠(b-c) + (-1/1)*∠(c-v) = 0
- eqangle(c,d,d,z,c,y,y,z): (-1/1)*∠(c-d) + (1/1)*∠(c-y) + (1/1)*∠(d-z) + (-1/1)*∠(y-z) = 0
- eqangle(a,v,v,z,a,w,w,z): (-1/1)*∠(a-v) + (1/1)*∠(a-w) + (1/1)*∠(v-z) + (-1/1)*∠(w-z) = 0

Assertions:
- eqangle(c,d,c,y,c,v,c,w): (-1/1)*∠(c-d) + (1/1)*∠(c-v) + (-1/1)*∠(c-w) + (1/1)*∠(c-y) = 0

### D073 `internal_theorem`

Dependencies: D072

Assumptions:
- eqangle(c,d,c,y,c,v,c,w)

Assertions:
- equation_class Yuclid::SinOrDist(d,c,y,v,c,w)

### D074 `ar:ratio chasing:sine_squared+squared_distance` [SINE-DISTANCE BRIDGE]

Dependencies: D053, D055, D059, D060, D061, D062, D073

Assumptions:
- equation_class Yuclid::SinOrDist(v,a,w,v,c,w): (1/1)*\sin² ∠(v a w) + (-1/1)*\sin² ∠(v c w) = 0
- equation_class Yuclid::SinOrDist(a,v,b,d,c,y): (1/1)*\sin² ∠(a v b) + (-1/1)*\sin² ∠(d c y) = 0
- equation_class Yuclid::SinOrDist(a,b,v,a,w,v): (1/1)*\sin² ∠(a b v) + (-1/1)*\sin² ∠(a w v) = 0
- equation_class Yuclid::SinOrDist(a,b,v,a,v,b,a,b,a,v): (1/1)*\sin² ∠(a b v) + (-1/1)*\sin² ∠(a v b) + (1/1)*|a-b|^2 + (-1/1)*|a-v|^2 = 0
- equation_class Yuclid::SinOrDist(a,v,w,v,a,w,a,w,v,w): (1/1)*\sin² ∠(a v w) + (-1/1)*\sin² ∠(v a w) + (-1/1)*|a-w|^2 + (1/1)*|v-w|^2 = 0
- equation_class Yuclid::SinOrDist(a,v,w,a,w,v,a,v,a,w): (1/1)*\sin² ∠(a v w) + (-1/1)*\sin² ∠(a w v) + (1/1)*|a-v|^2 + (-1/1)*|a-w|^2 = 0
- equation_class Yuclid::SinOrDist(d,c,y,v,c,w): (1/1)*\sin² ∠(d c y) + (-1/1)*\sin² ∠(v c w) = 0

Assertions:
- cong(a,b,v,w): (1/1)*|a-b|^2 + (-1/1)*|v-w|^2 = 0
