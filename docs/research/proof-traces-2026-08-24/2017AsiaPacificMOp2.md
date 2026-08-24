# 2017AsiaPacificMOp2: Yuclid proof trace

- Certificate: `C:\Users\81808\.openclaw\workspace\mortra-1-release\data\hageo-409-current-aux-bounded64-rerun-2026-08-24-runs\2017AsiaPacificMOp2.proof.json`
- Deductions read: 54
- Order: Yuclid certificate order; every deduction is retained.

## Complete deduction trace

### D000 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,d,b,e)

### D001 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,e,b,d)

### D002 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cong(a,z,c,z)

### D003 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cyclic(a,b,c,d)

### D004 `construction`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,c,a,d,a,d,a,b)

### D005 `construction`

Dependencies: none

Assumptions: none

Assertions:
- eqangle(a,c,c,z,a,z,a,c)

### D006 `construction`

Dependencies: none

Assumptions: none

Assertions:
- midp(n,a,b)

### D007 `construction`

Dependencies: none

Assumptions: none

Assertions:
- para(a,d,b,e)

### D008 `construction`

Dependencies: none

Assumptions: none

Assertions:
- para(a,e,b,d)

### D009 `construction`

Dependencies: none

Assumptions: none

Assertions:
- perp(a,d,a,z)

### D010 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(d,c,z,e,a,z)

### D011 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,n)

### D012 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,b)

### D013 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,n)

### D014 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,n,z)

### D015 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(b,c,d)

### D016 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,d,n)

### D017 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(b,e,n)

### D018 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(d,n,z)

### D019 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(e,n,z)

### D020 `dd:r56`

Dependencies: D006

Assumptions:
- midp(n,a,b)

Assertions:
- coll(a,b,n)

### D021 `dd:r55`

Dependencies: D006

Assumptions:
- midp(n,a,b)

Assertions:
- cong(a,n,b,n)

### D022 `dd:r03`

Dependencies: D003

Assumptions:
- cyclic(a,b,c,d)

Assertions:
- eqangle(a,c,a,d,b,c,b,d)

### D023 `dd:r03`

Dependencies: D003

Assumptions:
- cyclic(a,b,c,d)

Assertions:
- eqangle(a,b,b,d,a,c,c,d)

### D024 `internal_theorem`

Dependencies: D022

Assumptions:
- eqangle(a,c,a,d,b,c,b,d)

Assertions:
- equation_class Yuclid::SinOrDist(c,a,d,c,b,d)

### D025 `ar:angle chasing:directed_angle`

Dependencies: D004, D022, D023

Assumptions:
- eqangle(a,c,a,d,a,d,a,b): (-1/1)*∠(a-b) + (-1/1)*∠(a-c) + (2/1)*∠(a-d) = 0
- eqangle(a,c,a,d,b,c,b,d): (-1/1)*∠(a-c) + (1/1)*∠(a-d) + (1/1)*∠(b-c) + (-1/1)*∠(b-d) = 0
- eqangle(a,b,b,d,a,c,c,d): (-1/1)*∠(a-b) + (1/1)*∠(a-c) + (1/1)*∠(b-d) + (-1/1)*∠(c-d) = 0

Assertions:
- eqangle(b,c,c,d,a,d,a,c): (-1/1)*∠(a-c) + (1/1)*∠(a-d) + (-1/1)*∠(b-c) + (1/1)*∠(c-d) = 0

### D026 `internal_theorem`

Dependencies: D025

Assumptions:
- eqangle(b,c,c,d,a,d,a,c)

Assertions:
- equation_class Yuclid::SinOrDist(b,c,d,c,a,d)

### D027 `internal_theorem`

Dependencies: D015

Assumptions:
- ncoll(b,c,d)

Assertions:
- equation_class Yuclid::SinOrDist(b,c,d,c,b,d,b,d,c,d)

### D028 `internal_theorem`

Dependencies: D016

Assumptions:
- ncoll(a,d,n)

Assertions:
- equation_class Yuclid::SinOrDist(a,d,n,d,a,n,a,n,d,n)

### D029 `internal_theorem`

Dependencies: D016

Assumptions:
- ncoll(a,d,n)

Assertions:
- equation_class Yuclid::SinOrDist(a,d,n,a,n,d,a,d,a,n)

### D030 `internal_theorem`

Dependencies: D017

Assumptions:
- ncoll(b,e,n)

Assertions:
- equation_class Yuclid::SinOrDist(b,e,n,e,b,n,b,n,e,n)

### D031 `internal_theorem`

Dependencies: D017

Assumptions:
- ncoll(b,e,n)

Assertions:
- equation_class Yuclid::SinOrDist(b,e,n,b,n,e,b,e,b,n)

### D032 `internal_theorem`

Dependencies: D018

Assumptions:
- ncoll(d,n,z)

Assertions:
- equation_class Yuclid::SinOrDist(d,n,z,n,d,z,d,z,n,z)

### D033 `internal_theorem`

Dependencies: D019

Assumptions:
- ncoll(e,n,z)

Assertions:
- equation_class Yuclid::SinOrDist(e,n,z,n,e,z,e,z,n,z)

### D034 `ar:ratio chasing:sine_squared+squared_distance` [SINE-DISTANCE BRIDGE]

Dependencies: D001, D002, D024, D026, D027

Assumptions:
- cong(a,e,b,d): (1/1)*|a-e|^2 + (-1/1)*|b-d|^2 = 0
- cong(a,z,c,z): (1/1)*|a-z|^2 + (-1/1)*|c-z|^2 = 0
- equation_class Yuclid::SinOrDist(c,a,d,c,b,d): (1/1)*\sin² ∠(c a d) + (-1/1)*\sin² ∠(c b d) = 0
- equation_class Yuclid::SinOrDist(b,c,d,c,a,d): (1/1)*\sin² ∠(b c d) + (-1/1)*\sin² ∠(c a d) = 0
- equation_class Yuclid::SinOrDist(b,c,d,c,b,d,b,d,c,d): (1/1)*\sin² ∠(b c d) + (-1/1)*\sin² ∠(c b d) + (-1/1)*|b-d|^2 + (1/1)*|c-d|^2 = 0

Assertions:
- eqratio(a,e,a,z,c,d,c,z): (1/1)*|a-e|^2 + (-1/1)*|a-z|^2 + (-1/1)*|c-d|^2 + (1/1)*|c-z|^2 = 0

### D035 `ar:angle chasing:directed_angle`

Dependencies: D004, D005, D008, D009, D023

Assumptions:
- eqangle(a,c,a,d,a,d,a,b): (-1/1)*∠(a-b) + (-1/1)*∠(a-c) + (2/1)*∠(a-d) = 0
- eqangle(a,c,c,z,a,z,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-z) + (1/1)*∠(c-z) = 0
- para(a,e,b,d): (1/1)*∠(a-e) + (-1/1)*∠(b-d) = 0
- perp(a,d,a,z): (1/1)*∠(a-d) + (-1/1)*∠(a-z) = 0
- eqangle(a,b,b,d,a,c,c,d): (-1/1)*∠(a-b) + (1/1)*∠(a-c) + (1/1)*∠(b-d) + (-1/1)*∠(c-d) = 0

Assertions:
- eqangle(c,d,c,z,a,e,a,z): (1/1)*∠(a-e) + (-1/1)*∠(a-z) + (-1/1)*∠(c-d) + (1/1)*∠(c-z) = 0

### D036 `dd:r62`

Dependencies: D034, D035, D010

Assumptions:
- eqratio(a,e,a,z,c,d,c,z)
- eqangle(c,d,c,z,a,e,a,z)
- sameclock(d,c,z,e,a,z)

Assertions:
- simtri(a,e,z,c,d,z)

### D037 `dd:r52`

Dependencies: D036, D010

Assumptions:
- simtri(a,e,z,c,d,z)
- sameclock(d,c,z,e,a,z)

Assertions:
- eqangle(a,z,e,z,c,z,d,z)

### D038 `dd:r52`

Dependencies: D036, D010

Assumptions:
- simtri(a,e,z,c,d,z)
- sameclock(d,c,z,e,a,z)

Assertions:
- eqratio(a,e,c,d,e,z,d,z)

### D039 `dd:r82`

Dependencies: D020, D011, D012, D013

Assumptions:
- coll(a,b,n)
- diff(a,n)
- diff(a,b)
- diff(b,n)

Assertions:
- para(a,n,b,n)

### D040 `dd:r82`

Dependencies: D020, D011, D012, D013

Assumptions:
- coll(a,b,n)
- diff(a,n)
- diff(a,b)
- diff(b,n)

Assertions:
- para(a,b,a,n)

### D041 `internal_theorem`

Dependencies: D021, D020

Assumptions:
- cong(a,n,b,n)
- coll(a,b,n)

Assertions:
- equation_class Yuclid::SquaredDist(a,b,a,d,b,d,d,n)

### D042 `internal_theorem`

Dependencies: D021, D020

Assumptions:
- cong(a,n,b,n)
- coll(a,b,n)

Assertions:
- equation_class Yuclid::SquaredDist(a,b,a,e,b,e,e,n)

### D043 `ar:squared lengths chasing:squared_distance`

Dependencies: D000, D001, D041, D042

Assumptions:
- cong(a,d,b,e): (1/1)*|a-d|^2 + (-1/1)*|b-e|^2 = 0
- cong(a,e,b,d): (1/1)*|a-e|^2 + (-1/1)*|b-d|^2 = 0
- equation_class Yuclid::SquaredDist(a,b,a,d,b,d,d,n): (1/1)*|a-b|^2 + (-2/1)*|a-d|^2 + (-2/1)*|b-d|^2 + (4/1)*|d-n|^2 = 0
- equation_class Yuclid::SquaredDist(a,b,a,e,b,e,e,n): (1/1)*|a-b|^2 + (-2/1)*|a-e|^2 + (-2/1)*|b-e|^2 + (4/1)*|e-n|^2 = 0

Assertions:
- cong(d,n,e,n): (1/1)*|d-n|^2 + (-1/1)*|e-n|^2 = 0

### D044 `ar:angle chasing:directed_angle`

Dependencies: D007, D039

Assumptions:
- para(a,d,b,e): (1/1)*∠(a-d) + (-1/1)*∠(b-e) = 0
- para(a,n,b,n): (1/1)*∠(a-n) + (-1/1)*∠(b-n) = 0

Assertions:
- eqangle(a,d,a,n,b,e,b,n): (-1/1)*∠(a-d) + (1/1)*∠(a-n) + (1/1)*∠(b-e) + (-1/1)*∠(b-n) = 0

### D045 `internal_theorem`

Dependencies: D044

Assumptions:
- eqangle(a,d,a,n,b,e,b,n)

Assertions:
- equation_class Yuclid::SinOrDist(d,a,n,e,b,n)

### D046 `ar:ratio chasing:sine_squared+squared_distance` [SINE-DISTANCE BRIDGE]

Dependencies: D000, D028, D029, D030, D031, D043, D045

Assumptions:
- cong(a,d,b,e): (1/1)*|a-d|^2 + (-1/1)*|b-e|^2 = 0
- equation_class Yuclid::SinOrDist(a,d,n,d,a,n,a,n,d,n): (1/1)*\sin² ∠(a d n) + (-1/1)*\sin² ∠(d a n) + (-1/1)*|a-n|^2 + (1/1)*|d-n|^2 = 0
- equation_class Yuclid::SinOrDist(a,d,n,a,n,d,a,d,a,n): (1/1)*\sin² ∠(a d n) + (-1/1)*\sin² ∠(a n d) + (1/1)*|a-d|^2 + (-1/1)*|a-n|^2 = 0
- equation_class Yuclid::SinOrDist(b,e,n,e,b,n,b,n,e,n): (1/1)*\sin² ∠(b e n) + (-1/1)*\sin² ∠(e b n) + (-1/1)*|b-n|^2 + (1/1)*|e-n|^2 = 0
- equation_class Yuclid::SinOrDist(b,e,n,b,n,e,b,e,b,n): (1/1)*\sin² ∠(b e n) + (-1/1)*\sin² ∠(b n e) + (1/1)*|b-e|^2 + (-1/1)*|b-n|^2 = 0
- cong(d,n,e,n): (1/1)*|d-n|^2 + (-1/1)*|e-n|^2 = 0
- equation_class Yuclid::SinOrDist(d,a,n,e,b,n): (1/1)*\sin² ∠(d a n) + (-1/1)*\sin² ∠(e b n) = 0

Assertions:
- equation_class Yuclid::SinOrDist(a,n,d,b,n,e): (1/1)*\sin² ∠(a n d) + (-1/1)*\sin² ∠(b n e) = 0

### D047 `internal_theorem`

Dependencies: D046

Assumptions:
- equation_class Yuclid::SinOrDist(a,n,d,b,n,e)

Assertions:
- eqangle(a,n,d,n,b,n,e,n)

### D048 `ar:angle chasing:directed_angle`

Dependencies: D039, D047

Assumptions:
- para(a,n,b,n): (1/1)*∠(a-n) + (-1/1)*∠(b-n) = 0
- eqangle(a,n,d,n,b,n,e,n): (-1/1)*∠(a-n) + (1/1)*∠(b-n) + (1/1)*∠(d-n) + (-1/1)*∠(e-n) = 0

Assertions:
- eqangle(d,n,n,z,e,n,n,z): (-1/1)*∠(d-n) + (1/1)*∠(e-n) = 0

### D049 `internal_theorem`

Dependencies: D048

Assumptions:
- eqangle(d,n,n,z,e,n,n,z)

Assertions:
- equation_class Yuclid::SinOrDist(d,n,z,e,n,z)

### D050 `ar:ratio chasing:sine_squared+squared_distance` [SINE-DISTANCE BRIDGE]

Dependencies: D001, D024, D026, D027, D032, D033, D038, D049

Assumptions:
- cong(a,e,b,d): (1/1)*|a-e|^2 + (-1/1)*|b-d|^2 = 0
- equation_class Yuclid::SinOrDist(c,a,d,c,b,d): (1/1)*\sin² ∠(c a d) + (-1/1)*\sin² ∠(c b d) = 0
- equation_class Yuclid::SinOrDist(b,c,d,c,a,d): (1/1)*\sin² ∠(b c d) + (-1/1)*\sin² ∠(c a d) = 0
- equation_class Yuclid::SinOrDist(b,c,d,c,b,d,b,d,c,d): (1/1)*\sin² ∠(b c d) + (-1/1)*\sin² ∠(c b d) + (-1/1)*|b-d|^2 + (1/1)*|c-d|^2 = 0
- equation_class Yuclid::SinOrDist(d,n,z,n,d,z,d,z,n,z): (1/1)*\sin² ∠(d n z) + (-1/1)*\sin² ∠(n d z) + (-1/1)*|d-z|^2 + (1/1)*|n-z|^2 = 0
- equation_class Yuclid::SinOrDist(e,n,z,n,e,z,e,z,n,z): (1/1)*\sin² ∠(e n z) + (-1/1)*\sin² ∠(n e z) + (-1/1)*|e-z|^2 + (1/1)*|n-z|^2 = 0
- eqratio(a,e,c,d,e,z,d,z): (1/1)*|a-e|^2 + (-1/1)*|c-d|^2 + (1/1)*|d-z|^2 + (-1/1)*|e-z|^2 = 0
- equation_class Yuclid::SinOrDist(d,n,z,e,n,z): (1/1)*\sin² ∠(d n z) + (-1/1)*\sin² ∠(e n z) = 0

Assertions:
- equation_class Yuclid::SinOrDist(n,d,z,n,e,z): (1/1)*\sin² ∠(n d z) + (-1/1)*\sin² ∠(n e z) = 0

### D051 `internal_theorem`

Dependencies: D050

Assumptions:
- equation_class Yuclid::SinOrDist(n,d,z,n,e,z)

Assertions:
- eqangle(d,n,d,z,e,z,e,n)

### D052 `ar:angle chasing:directed_angle`

Dependencies: D004, D005, D009, D037, D039, D040, D047, D051

Assumptions:
- eqangle(a,c,a,d,a,d,a,b): (-1/1)*∠(a-b) + (-1/1)*∠(a-c) + (2/1)*∠(a-d) = 0
- eqangle(a,c,c,z,a,z,a,c): (-2/1)*∠(a-c) + (1/1)*∠(a-z) + (1/1)*∠(c-z) = 0
- perp(a,d,a,z): (1/1)*∠(a-d) + (-1/1)*∠(a-z) = 0
- eqangle(a,z,e,z,c,z,d,z): (-1/1)*∠(a-z) + (1/1)*∠(c-z) + (-1/1)*∠(d-z) + (1/1)*∠(e-z) = 0
- para(a,n,b,n): (1/1)*∠(a-n) + (-1/1)*∠(b-n) = 0
- para(a,b,a,n): (1/1)*∠(a-b) + (-1/1)*∠(a-n) = 0
- eqangle(a,n,d,n,b,n,e,n): (-1/1)*∠(a-n) + (1/1)*∠(b-n) + (1/1)*∠(d-n) + (-1/1)*∠(e-n) = 0
- eqangle(d,n,d,z,e,z,e,n): (-1/1)*∠(d-n) + (1/1)*∠(d-z) + (-1/1)*∠(e-n) + (1/1)*∠(e-z) = 0

Assertions:
- eqangle(a,n,a,z,d,n,d,z): (-1/1)*∠(a-n) + (1/1)*∠(a-z) + (1/1)*∠(d-n) + (-1/1)*∠(d-z) = 0

### D053 `dd:r04`

Dependencies: D052, D014

Assumptions:
- eqangle(a,n,a,z,d,n,d,z)
- ncoll(a,n,z)

Assertions:
- cyclic(a,d,n,z)
