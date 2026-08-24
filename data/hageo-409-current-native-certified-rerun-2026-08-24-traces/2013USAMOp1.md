# 2013USAMOp1: Yuclid proof trace

- Certificate: `data/hageo-409-current-native-certified-rerun-2026-08-24-runs/proofs/2013USAMOp1.json`
- Deductions read: 140
- Order: Yuclid certificate order; every deduction is retained.

## Complete deduction trace

### D000 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(a,b,r)

### D001 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(a,c,q)

### D002 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(a,p,x)

### D003 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(a,p,y)

### D004 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(a,p,z)

### D005 `construction`

Dependencies: none

Assumptions: none

Assertions:
- coll(b,c,p)

### D006 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cyclic(a,q,r,x)

### D007 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cyclic(b,p,r,y)

### D008 `construction`

Dependencies: none

Assumptions: none

Assertions:
- cyclic(c,p,q,z)

### D009 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(a,y,b,a,p,r)

### D010 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(p,b,a,r,a,y)

### D011 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- sameclock(b,a,p,y,r,a)

### D012 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,r)

### D013 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,b)

### D014 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,r)

### D015 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,p)

### D016 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(b,c)

### D017 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(c,p)

### D018 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,q)

### D019 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,c)

### D020 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(c,q)

### D021 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,x)

### D022 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,p)

### D023 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(p,x)

### D024 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,y)

### D025 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(p,y)

### D026 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(x,y)

### D027 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(a,z)

### D028 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(p,z)

### D029 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(x,z)

### D030 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- diff(y,z)

### D031 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,b,c)

### D032 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,b,p)

### D033 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,c,p)

### D034 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,p,q)

### D035 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,p,r)

### D036 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,q,r)

### D037 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,b,y)

### D038 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(r,x,y)

### D039 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,c,z)

### D040 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(a,q,z)

### D041 `numerical_guard`

Dependencies: none

Assumptions: none

Assertions:
- ncoll(q,x,z)

### D042 `dd:r82`

Dependencies: D000, D012, D013, D014

Assumptions:
- coll(a,b,r)
- diff(a,r)
- diff(a,b)
- diff(b,r)

Assertions:
- para(a,r,b,r)

### D043 `dd:r82`

Dependencies: D000, D012, D013, D014

Assumptions:
- coll(a,b,r)
- diff(a,r)
- diff(a,b)
- diff(b,r)

Assertions:
- para(a,b,a,r)

### D044 `dd:r82`

Dependencies: D005, D015, D016, D017

Assumptions:
- coll(b,c,p)
- diff(b,p)
- diff(b,c)
- diff(c,p)

Assertions:
- para(b,p,c,p)

### D045 `dd:r82`

Dependencies: D005, D015, D016, D017

Assumptions:
- coll(b,c,p)
- diff(b,p)
- diff(b,c)
- diff(c,p)

Assertions:
- para(b,c,b,p)

### D046 `dd:r82`

Dependencies: D001, D018, D019, D020

Assumptions:
- coll(a,c,q)
- diff(a,q)
- diff(a,c)
- diff(c,q)

Assertions:
- para(a,q,c,q)

### D047 `dd:r82`

Dependencies: D001, D018, D019, D020

Assumptions:
- coll(a,c,q)
- diff(a,q)
- diff(a,c)
- diff(c,q)

Assertions:
- para(a,c,a,q)

### D048 `dd:r82`

Dependencies: D002, D021, D022, D023

Assumptions:
- coll(a,p,x)
- diff(a,x)
- diff(a,p)
- diff(p,x)

Assertions:
- para(a,x,p,x)

### D049 `dd:r82`

Dependencies: D002, D021, D022, D023

Assumptions:
- coll(a,p,x)
- diff(a,x)
- diff(a,p)
- diff(p,x)

Assertions:
- para(a,p,a,x)

### D050 `dd:r82`

Dependencies: D003, D024, D022, D025

Assumptions:
- coll(a,p,y)
- diff(a,y)
- diff(a,p)
- diff(p,y)

Assertions:
- para(a,y,p,y)

### D051 `dd:r82`

Dependencies: D003, D024, D022, D025

Assumptions:
- coll(a,p,y)
- diff(a,y)
- diff(a,p)
- diff(p,y)

Assertions:
- para(a,p,a,y)

### D052 `ar:angle chasing:directed_angle`

Dependencies: D049, D051

Assumptions:
- para(a,p,a,x): (1/1)*∠(a-p) + (-1/1)*∠(a-x) = 0
- para(a,p,a,y): (1/1)*∠(a-p) + (-1/1)*∠(a-y) = 0

Assertions:
- para(a,x,a,y): (1/1)*∠(a-x) + (-1/1)*∠(a-y) = 0

### D053 `dd:r28`

Dependencies: D052

Assumptions:
- para(a,x,a,y)

Assertions:
- coll(a,x,y)

### D054 `dd:r82`

Dependencies: D053, D021, D026, D024

Assumptions:
- coll(a,x,y)
- diff(a,x)
- diff(x,y)
- diff(a,y)

Assertions:
- para(a,x,x,y)

### D055 `dd:r82`

Dependencies: D004, D022, D027, D028

Assumptions:
- coll(a,p,z)
- diff(a,p)
- diff(a,z)
- diff(p,z)

Assertions:
- para(a,p,p,z)

### D056 `dd:r82`

Dependencies: D004, D022, D027, D028

Assumptions:
- coll(a,p,z)
- diff(a,p)
- diff(a,z)
- diff(p,z)

Assertions:
- para(a,p,a,z)

### D057 `ar:angle chasing:directed_angle`

Dependencies: D048, D049, D055

Assumptions:
- para(a,x,p,x): (1/1)*∠(a-x) + (-1/1)*∠(p-x) = 0
- para(a,p,a,x): (1/1)*∠(a-p) + (-1/1)*∠(a-x) = 0
- para(a,p,p,z): (1/1)*∠(a-p) + (-1/1)*∠(p-z) = 0

Assertions:
- para(p,x,p,z): (1/1)*∠(p-x) + (-1/1)*∠(p-z) = 0

### D058 `dd:r28`

Dependencies: D057

Assumptions:
- para(p,x,p,z)

Assertions:
- coll(p,x,z)

### D059 `dd:r82`

Dependencies: D058, D023, D029, D028

Assumptions:
- coll(p,x,z)
- diff(p,x)
- diff(x,z)
- diff(p,z)

Assertions:
- para(p,x,x,z)

### D060 `ar:angle chasing:directed_angle`

Dependencies: D050, D051, D055

Assumptions:
- para(a,y,p,y): (1/1)*∠(a-y) + (-1/1)*∠(p-y) = 0
- para(a,p,a,y): (1/1)*∠(a-p) + (-1/1)*∠(a-y) = 0
- para(a,p,p,z): (1/1)*∠(a-p) + (-1/1)*∠(p-z) = 0

Assertions:
- para(p,y,p,z): (1/1)*∠(p-y) + (-1/1)*∠(p-z) = 0

### D061 `dd:r28`

Dependencies: D060

Assumptions:
- para(p,y,p,z)

Assertions:
- coll(p,y,z)

### D062 `dd:r82`

Dependencies: D061, D025, D030, D028

Assumptions:
- coll(p,y,z)
- diff(p,y)
- diff(y,z)
- diff(p,z)

Assertions:
- para(p,y,y,z)

### D063 `ar:angle chasing:directed_angle`

Dependencies: D042, D043

Assumptions:
- para(a,r,b,r): (1/1)*∠(a-r) + (-1/1)*∠(b-r) = 0
- para(a,b,a,r): (1/1)*∠(a-b) + (-1/1)*∠(a-r) = 0

Assertions:
- eqangle(a,b,b,y,b,r,b,y): (-1/1)*∠(a-b) + (1/1)*∠(b-r) = 0

### D064 `internal_theorem`

Dependencies: D063

Assumptions:
- eqangle(a,b,b,y,b,r,b,y)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,y,r,b,y)

### D065 `ar:angle chasing:directed_angle`

Dependencies: D055

Assumptions:
- para(a,p,p,z): (1/1)*∠(a-p) + (-1/1)*∠(p-z) = 0

Assertions:
- eqangle(a,p,p,r,p,z,p,r): (-1/1)*∠(a-p) + (1/1)*∠(p-z) = 0

### D066 `internal_theorem`

Dependencies: D065

Assumptions:
- eqangle(a,p,p,r,p,z,p,r)

Assertions:
- equation_class Yuclid::SinOrDist(a,p,r,r,p,z)

### D067 `ar:angle chasing:directed_angle`

Dependencies: D050, D051, D055

Assumptions:
- para(a,y,p,y): (1/1)*∠(a-y) + (-1/1)*∠(p-y) = 0
- para(a,p,a,y): (1/1)*∠(a-p) + (-1/1)*∠(a-y) = 0
- para(a,p,p,z): (1/1)*∠(a-p) + (-1/1)*∠(p-z) = 0

Assertions:
- eqangle(p,r,p,y,p,r,p,z): (1/1)*∠(p-y) + (-1/1)*∠(p-z) = 0

### D068 `internal_theorem`

Dependencies: D067

Assumptions:
- eqangle(p,r,p,y,p,r,p,z)

Assertions:
- equation_class Yuclid::SinOrDist(r,p,y,r,p,z)

### D069 `ar:angle chasing:directed_angle`

Dependencies: D046

Assumptions:
- para(a,q,c,q): (1/1)*∠(a-q) + (-1/1)*∠(c-q) = 0

Assertions:
- eqangle(a,q,q,r,c,q,q,r): (-1/1)*∠(a-q) + (1/1)*∠(c-q) = 0

### D070 `internal_theorem`

Dependencies: D069

Assumptions:
- eqangle(a,q,q,r,c,q,q,r)

Assertions:
- equation_class Yuclid::SinOrDist(a,q,r,c,q,r)

### D071 `ar:angle chasing:directed_angle`

Dependencies: D047

Assumptions:
- para(a,c,a,q): (1/1)*∠(a-c) + (-1/1)*∠(a-q) = 0

Assertions:
- eqangle(a,c,a,p,a,q,a,p): (-1/1)*∠(a-c) + (1/1)*∠(a-q) = 0

### D072 `internal_theorem`

Dependencies: D071

Assumptions:
- eqangle(a,c,a,p,a,q,a,p)

Assertions:
- equation_class Yuclid::SinOrDist(c,a,p,p,a,q)

### D073 `ar:angle chasing:directed_angle`

Dependencies: D056

Assumptions:
- para(a,p,a,z): (1/1)*∠(a-p) + (-1/1)*∠(a-z) = 0

Assertions:
- eqangle(a,p,a,q,a,z,a,q): (-1/1)*∠(a-p) + (1/1)*∠(a-z) = 0

### D074 `internal_theorem`

Dependencies: D073

Assumptions:
- eqangle(a,p,a,q,a,z,a,q)

Assertions:
- equation_class Yuclid::SinOrDist(p,a,q,q,a,z)

### D075 `ar:angle chasing:directed_angle`

Dependencies: D051, D056

Assumptions:
- para(a,p,a,y): (1/1)*∠(a-p) + (-1/1)*∠(a-y) = 0
- para(a,p,a,z): (1/1)*∠(a-p) + (-1/1)*∠(a-z) = 0

Assertions:
- eqangle(a,b,a,y,a,b,a,z): (1/1)*∠(a-y) + (-1/1)*∠(a-z) = 0

### D076 `internal_theorem`

Dependencies: D075

Assumptions:
- eqangle(a,b,a,y,a,b,a,z)

Assertions:
- equation_class Yuclid::SinOrDist(b,a,y,b,a,z)

### D077 `ar:angle chasing:directed_angle`

Dependencies: D043, D056

Assumptions:
- para(a,b,a,r): (1/1)*∠(a-b) + (-1/1)*∠(a-r) = 0
- para(a,p,a,z): (1/1)*∠(a-p) + (-1/1)*∠(a-z) = 0

Assertions:
- eqangle(a,b,a,z,a,r,a,p): (-1/1)*∠(a-b) + (-1/1)*∠(a-p) + (1/1)*∠(a-r) + (1/1)*∠(a-z) = 0

### D078 `internal_theorem`

Dependencies: D077

Assumptions:
- eqangle(a,b,a,z,a,r,a,p)

Assertions:
- equation_class Yuclid::SinOrDist(b,a,z,p,a,r)

### D079 `ar:angle chasing:directed_angle`

Dependencies: D043, D051

Assumptions:
- para(a,b,a,r): (1/1)*∠(a-b) + (-1/1)*∠(a-r) = 0
- para(a,p,a,y): (1/1)*∠(a-p) + (-1/1)*∠(a-y) = 0

Assertions:
- eqangle(a,b,a,p,a,r,a,y): (-1/1)*∠(a-b) + (1/1)*∠(a-p) + (1/1)*∠(a-r) + (-1/1)*∠(a-y) = 0

### D080 `dd:r03`

Dependencies: D006

Assumptions:
- cyclic(a,q,r,x)

Assertions:
- eqangle(a,r,a,x,q,r,q,x)

### D081 `dd:r03`

Dependencies: D006

Assumptions:
- cyclic(a,q,r,x)

Assertions:
- eqangle(a,q,a,x,q,r,r,x)

### D082 `ar:angle chasing:directed_angle`

Dependencies: D044, D045

Assumptions:
- para(b,p,c,p): (1/1)*∠(b-p) + (-1/1)*∠(c-p) = 0
- para(b,c,b,p): (1/1)*∠(b-c) + (-1/1)*∠(b-p) = 0

Assertions:
- eqangle(a,c,b,c,a,c,c,p): (1/1)*∠(b-c) + (-1/1)*∠(c-p) = 0

### D083 `internal_theorem`

Dependencies: D082

Assumptions:
- eqangle(a,c,b,c,a,c,c,p)

Assertions:
- equation_class Yuclid::SinOrDist(a,c,b,a,c,p)

### D084 `ar:angle chasing:directed_angle`

Dependencies: D046

Assumptions:
- para(a,q,c,q): (1/1)*∠(a-q) + (-1/1)*∠(c-q) = 0

Assertions:
- eqangle(a,q,p,q,c,q,p,q): (-1/1)*∠(a-q) + (1/1)*∠(c-q) = 0

### D085 `internal_theorem`

Dependencies: D084

Assumptions:
- eqangle(a,q,p,q,c,q,p,q)

Assertions:
- equation_class Yuclid::SinOrDist(a,q,p,c,q,p)

### D086 `ar:angle chasing:directed_angle`

Dependencies: D050, D051, D056, D062

Assumptions:
- para(a,y,p,y): (1/1)*∠(a-y) + (-1/1)*∠(p-y) = 0
- para(a,p,a,y): (1/1)*∠(a-p) + (-1/1)*∠(a-y) = 0
- para(a,p,a,z): (1/1)*∠(a-p) + (-1/1)*∠(a-z) = 0
- para(p,y,y,z): (1/1)*∠(p-y) + (-1/1)*∠(y-z) = 0

Assertions:
- eqangle(a,z,c,z,y,z,c,z): (-1/1)*∠(a-z) + (1/1)*∠(y-z) = 0

### D087 `internal_theorem`

Dependencies: D086

Assumptions:
- eqangle(a,z,c,z,y,z,c,z)

Assertions:
- equation_class Yuclid::SinOrDist(a,z,c,c,z,y)

### D088 `ar:angle chasing:directed_angle`

Dependencies: D048, D049, D050, D051, D059, D062

Assumptions:
- para(a,x,p,x): (1/1)*∠(a-x) + (-1/1)*∠(p-x) = 0
- para(a,p,a,x): (1/1)*∠(a-p) + (-1/1)*∠(a-x) = 0
- para(a,y,p,y): (1/1)*∠(a-y) + (-1/1)*∠(p-y) = 0
- para(a,p,a,y): (1/1)*∠(a-p) + (-1/1)*∠(a-y) = 0
- para(p,x,x,z): (1/1)*∠(p-x) + (-1/1)*∠(x-z) = 0
- para(p,y,y,z): (1/1)*∠(p-y) + (-1/1)*∠(y-z) = 0

Assertions:
- eqangle(c,z,x,z,c,z,y,z): (1/1)*∠(x-z) + (-1/1)*∠(y-z) = 0

### D089 `internal_theorem`

Dependencies: D088

Assumptions:
- eqangle(c,z,x,z,c,z,y,z)

Assertions:
- equation_class Yuclid::SinOrDist(c,z,x,c,z,y)

### D090 `ar:angle chasing:directed_angle`

Dependencies: D055

Assumptions:
- para(a,p,p,z): (1/1)*∠(a-p) + (-1/1)*∠(p-z) = 0

Assertions:
- eqangle(a,p,b,p,p,z,b,p): (-1/1)*∠(a-p) + (1/1)*∠(p-z) = 0

### D091 `internal_theorem`

Dependencies: D090

Assumptions:
- eqangle(a,p,b,p,p,z,b,p)

Assertions:
- equation_class Yuclid::SinOrDist(a,p,b,b,p,z)

### D092 `ar:angle chasing:directed_angle`

Dependencies: D044, D048, D049, D055

Assumptions:
- para(b,p,c,p): (1/1)*∠(b-p) + (-1/1)*∠(c-p) = 0
- para(a,x,p,x): (1/1)*∠(a-x) + (-1/1)*∠(p-x) = 0
- para(a,p,a,x): (1/1)*∠(a-p) + (-1/1)*∠(a-x) = 0
- para(a,p,p,z): (1/1)*∠(a-p) + (-1/1)*∠(p-z) = 0

Assertions:
- eqangle(b,p,p,z,c,p,p,x): (-1/1)*∠(b-p) + (1/1)*∠(c-p) + (-1/1)*∠(p-x) + (1/1)*∠(p-z) = 0

### D093 `internal_theorem`

Dependencies: D092

Assumptions:
- eqangle(b,p,p,z,c,p,p,x)

Assertions:
- equation_class Yuclid::SinOrDist(b,p,z,c,p,x)

### D094 `ar:angle chasing:directed_angle`

Dependencies: D046

Assumptions:
- para(a,q,c,q): (1/1)*∠(a-q) + (-1/1)*∠(c-q) = 0

Assertions:
- eqangle(a,q,q,z,c,q,q,z): (-1/1)*∠(a-q) + (1/1)*∠(c-q) = 0

### D095 `internal_theorem`

Dependencies: D094

Assumptions:
- eqangle(a,q,q,z,c,q,q,z)

Assertions:
- equation_class Yuclid::SinOrDist(a,q,z,c,q,z)

### D096 `ar:angle chasing:directed_angle`

Dependencies: D045

Assumptions:
- para(b,c,b,p): (1/1)*∠(b-c) + (-1/1)*∠(b-p) = 0

Assertions:
- eqangle(a,b,b,c,a,b,b,p): (1/1)*∠(b-c) + (-1/1)*∠(b-p) = 0

### D097 `internal_theorem`

Dependencies: D096

Assumptions:
- eqangle(a,b,b,c,a,b,b,p)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,c,a,b,p)

### D098 `ar:angle chasing:directed_angle`

Dependencies: D046, D047

Assumptions:
- para(a,q,c,q): (1/1)*∠(a-q) + (-1/1)*∠(c-q) = 0
- para(a,c,a,q): (1/1)*∠(a-c) + (-1/1)*∠(a-q) = 0

Assertions:
- eqangle(a,c,c,z,c,q,c,z): (-1/1)*∠(a-c) + (1/1)*∠(c-q) = 0

### D099 `internal_theorem`

Dependencies: D098

Assumptions:
- eqangle(a,c,c,z,c,q,c,z)

Assertions:
- equation_class Yuclid::SinOrDist(a,c,z,q,c,z)

### D100 `dd:r03`

Dependencies: D008

Assumptions:
- cyclic(c,p,q,z)

Assertions:
- eqangle(c,q,c,z,p,q,p,z)

### D101 `dd:r03`

Dependencies: D008

Assumptions:
- cyclic(c,p,q,z)

Assertions:
- eqangle(c,p,c,z,p,q,q,z)

### D102 `internal_theorem`

Dependencies: D100

Assumptions:
- eqangle(c,q,c,z,p,q,p,z)

Assertions:
- equation_class Yuclid::SinOrDist(q,c,z,q,p,z)

### D103 `ar:angle chasing:directed_angle`

Dependencies: D048, D049

Assumptions:
- para(a,x,p,x): (1/1)*∠(a-x) + (-1/1)*∠(p-x) = 0
- para(a,p,a,x): (1/1)*∠(a-p) + (-1/1)*∠(a-x) = 0

Assertions:
- eqangle(a,p,p,q,p,x,p,q): (-1/1)*∠(a-p) + (1/1)*∠(p-x) = 0

### D104 `internal_theorem`

Dependencies: D103

Assumptions:
- eqangle(a,p,p,q,p,x,p,q)

Assertions:
- equation_class Yuclid::SinOrDist(a,p,q,q,p,x)

### D105 `ar:angle chasing:directed_angle`

Dependencies: D048, D049, D055

Assumptions:
- para(a,x,p,x): (1/1)*∠(a-x) + (-1/1)*∠(p-x) = 0
- para(a,p,a,x): (1/1)*∠(a-p) + (-1/1)*∠(a-x) = 0
- para(a,p,p,z): (1/1)*∠(a-p) + (-1/1)*∠(p-z) = 0

Assertions:
- eqangle(p,q,p,x,p,q,p,z): (1/1)*∠(p-x) + (-1/1)*∠(p-z) = 0

### D106 `internal_theorem`

Dependencies: D105

Assumptions:
- eqangle(p,q,p,x,p,q,p,z)

Assertions:
- equation_class Yuclid::SinOrDist(q,p,x,q,p,z)

### D107 `ar:angle chasing:directed_angle`

Dependencies: D042

Assumptions:
- para(a,r,b,r): (1/1)*∠(a-r) + (-1/1)*∠(b-r) = 0

Assertions:
- eqangle(a,r,q,r,b,r,q,r): (-1/1)*∠(a-r) + (1/1)*∠(b-r) = 0

### D108 `internal_theorem`

Dependencies: D107

Assumptions:
- eqangle(a,r,q,r,b,r,q,r)

Assertions:
- equation_class Yuclid::SinOrDist(a,r,q,b,r,q)

### D109 `ar:angle chasing:directed_angle`

Dependencies: D042, D048, D059, D080

Assumptions:
- para(a,r,b,r): (1/1)*∠(a-r) + (-1/1)*∠(b-r) = 0
- para(a,x,p,x): (1/1)*∠(a-x) + (-1/1)*∠(p-x) = 0
- para(p,x,x,z): (1/1)*∠(p-x) + (-1/1)*∠(x-z) = 0
- eqangle(a,r,a,x,q,r,q,x): (-1/1)*∠(a-r) + (1/1)*∠(a-x) + (1/1)*∠(q-r) + (-1/1)*∠(q-x) = 0

Assertions:
- eqangle(b,r,q,r,x,z,q,x): (-1/1)*∠(b-r) + (1/1)*∠(q-r) + (-1/1)*∠(q-x) + (1/1)*∠(x-z) = 0

### D110 `internal_theorem`

Dependencies: D109

Assumptions:
- eqangle(b,r,q,r,x,z,q,x)

Assertions:
- equation_class Yuclid::SinOrDist(b,r,q,q,x,z)

### D111 `ar:angle chasing:directed_angle`

Dependencies: D048, D049, D055, D100, D101

Assumptions:
- para(a,x,p,x): (1/1)*∠(a-x) + (-1/1)*∠(p-x) = 0
- para(a,p,a,x): (1/1)*∠(a-p) + (-1/1)*∠(a-x) = 0
- para(a,p,p,z): (1/1)*∠(a-p) + (-1/1)*∠(p-z) = 0
- eqangle(c,q,c,z,p,q,p,z): (-1/1)*∠(c-q) + (1/1)*∠(c-z) + (1/1)*∠(p-q) + (-1/1)*∠(p-z) = 0
- eqangle(c,p,c,z,p,q,q,z): (-1/1)*∠(c-p) + (1/1)*∠(c-z) + (1/1)*∠(p-q) + (-1/1)*∠(q-z) = 0

Assertions:
- eqangle(c,p,p,x,c,q,q,z): (-1/1)*∠(c-p) + (1/1)*∠(c-q) + (1/1)*∠(p-x) + (-1/1)*∠(q-z) = 0

### D112 `internal_theorem`

Dependencies: D111

Assumptions:
- eqangle(c,p,p,x,c,q,q,z)

Assertions:
- equation_class Yuclid::SinOrDist(c,p,x,c,q,z)

### D113 `ar:angle chasing:directed_angle`

Dependencies: D048, D049, D055, D059, D100

Assumptions:
- para(a,x,p,x): (1/1)*∠(a-x) + (-1/1)*∠(p-x) = 0
- para(a,p,a,x): (1/1)*∠(a-p) + (-1/1)*∠(a-x) = 0
- para(a,p,p,z): (1/1)*∠(a-p) + (-1/1)*∠(p-z) = 0
- para(p,x,x,z): (1/1)*∠(p-x) + (-1/1)*∠(x-z) = 0
- eqangle(c,q,c,z,p,q,p,z): (-1/1)*∠(c-q) + (1/1)*∠(c-z) + (1/1)*∠(p-q) + (-1/1)*∠(p-z) = 0

Assertions:
- eqangle(c,q,p,q,c,z,x,z): (-1/1)*∠(c-q) + (1/1)*∠(c-z) + (1/1)*∠(p-q) + (-1/1)*∠(x-z) = 0

### D114 `internal_theorem`

Dependencies: D113

Assumptions:
- eqangle(c,q,p,q,c,z,x,z)

Assertions:
- equation_class Yuclid::SinOrDist(c,q,p,c,z,x)

### D115 `ar:angle chasing:directed_angle`

Dependencies: D046, D054, D081

Assumptions:
- para(a,q,c,q): (1/1)*∠(a-q) + (-1/1)*∠(c-q) = 0
- para(a,x,x,y): (1/1)*∠(a-x) + (-1/1)*∠(x-y) = 0
- eqangle(a,q,a,x,q,r,r,x): (-1/1)*∠(a-q) + (1/1)*∠(a-x) + (1/1)*∠(q-r) + (-1/1)*∠(r-x) = 0

Assertions:
- eqangle(c,q,q,r,x,y,r,x): (-1/1)*∠(c-q) + (1/1)*∠(q-r) + (-1/1)*∠(r-x) + (1/1)*∠(x-y) = 0

### D116 `internal_theorem`

Dependencies: D115

Assumptions:
- eqangle(c,q,q,r,x,y,r,x)

Assertions:
- equation_class Yuclid::SinOrDist(c,q,r,r,x,y)

### D117 `dd:r03`

Dependencies: D007

Assumptions:
- cyclic(b,p,r,y)

Assertions:
- eqangle(b,r,b,y,p,r,p,y)

### D118 `dd:r03`

Dependencies: D007

Assumptions:
- cyclic(b,p,r,y)

Assertions:
- eqangle(b,p,p,y,b,r,r,y)

### D119 `internal_theorem`

Dependencies: D117

Assumptions:
- eqangle(b,r,b,y,p,r,p,y)

Assertions:
- equation_class Yuclid::SinOrDist(r,b,y,r,p,y)

### D120 `internal_theorem`

Dependencies: D031

Assumptions:
- ncoll(a,b,c)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,c,a,c,b,a,b,a,c)

### D121 `internal_theorem`

Dependencies: D032

Assumptions:
- ncoll(a,b,p)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,p,a,p,b,a,b,a,p)

### D122 `internal_theorem`

Dependencies: D033

Assumptions:
- ncoll(a,c,p)

Assertions:
- equation_class Yuclid::SinOrDist(a,c,p,c,a,p,a,p,c,p)

### D123 `internal_theorem`

Dependencies: D034

Assumptions:
- ncoll(a,p,q)

Assertions:
- equation_class Yuclid::SinOrDist(a,p,q,a,q,p,a,p,a,q)

### D124 `internal_theorem`

Dependencies: D035

Assumptions:
- ncoll(a,p,r)

Assertions:
- equation_class Yuclid::SinOrDist(a,p,r,p,a,r,a,r,p,r)

### D125 `internal_theorem`

Dependencies: D036

Assumptions:
- ncoll(a,q,r)

Assertions:
- equation_class Yuclid::SinOrDist(a,q,r,a,r,q,a,q,a,r)

### D126 `internal_theorem`

Dependencies: D037

Assumptions:
- ncoll(a,b,y)

Assertions:
- equation_class Yuclid::SinOrDist(a,b,y,b,a,y,a,y,b,y)

### D127 `internal_theorem`

Dependencies: D038

Assumptions:
- ncoll(r,x,y)

Assertions:
- equation_class Yuclid::SinOrDist(r,x,y,x,r,y,r,y,x,y)

### D128 `internal_theorem`

Dependencies: D039

Assumptions:
- ncoll(a,c,z)

Assertions:
- equation_class Yuclid::SinOrDist(a,c,z,a,z,c,a,c,a,z)

### D129 `internal_theorem`

Dependencies: D040

Assumptions:
- ncoll(a,q,z)

Assertions:
- equation_class Yuclid::SinOrDist(a,q,z,q,a,z,a,z,q,z)

### D130 `internal_theorem`

Dependencies: D041

Assumptions:
- ncoll(q,x,z)

Assertions:
- equation_class Yuclid::SinOrDist(q,x,z,x,q,z,q,z,x,z)

### D131 `ar:ratio chasing:sine_squared+squared_distance` [SINE-DISTANCE BRIDGE]

Dependencies: D064, D066, D068, D076, D078, D119, D124, D126

Assumptions:
- equation_class Yuclid::SinOrDist(a,b,y,r,b,y): (1/1)*\sin² ∠(a b y) + (-1/1)*\sin² ∠(r b y) = 0
- equation_class Yuclid::SinOrDist(a,p,r,r,p,z): (1/1)*\sin² ∠(a p r) + (-1/1)*\sin² ∠(r p z) = 0
- equation_class Yuclid::SinOrDist(r,p,y,r,p,z): (1/1)*\sin² ∠(r p y) + (-1/1)*\sin² ∠(r p z) = 0
- equation_class Yuclid::SinOrDist(b,a,y,b,a,z): (1/1)*\sin² ∠(b a y) + (-1/1)*\sin² ∠(b a z) = 0
- equation_class Yuclid::SinOrDist(b,a,z,p,a,r): (1/1)*\sin² ∠(b a z) + (-1/1)*\sin² ∠(p a r) = 0
- equation_class Yuclid::SinOrDist(r,b,y,r,p,y): (1/1)*\sin² ∠(r b y) + (-1/1)*\sin² ∠(r p y) = 0
- equation_class Yuclid::SinOrDist(a,p,r,p,a,r,a,r,p,r): (1/1)*\sin² ∠(a p r) + (-1/1)*\sin² ∠(p a r) + (-1/1)*|a-r|^2 + (1/1)*|p-r|^2 = 0
- equation_class Yuclid::SinOrDist(a,b,y,b,a,y,a,y,b,y): (1/1)*\sin² ∠(a b y) + (-1/1)*\sin² ∠(b a y) + (-1/1)*|a-y|^2 + (1/1)*|b-y|^2 = 0

Assertions:
- eqratio(a,r,a,y,p,r,b,y): (1/1)*|a-r|^2 + (-1/1)*|a-y|^2 + (1/1)*|b-y|^2 + (-1/1)*|p-r|^2 = 0

### D132 `ar:angle chasing:directed_angle`

Dependencies: D042, D050, D117

Assumptions:
- para(a,r,b,r): (1/1)*∠(a-r) + (-1/1)*∠(b-r) = 0
- para(a,y,p,y): (1/1)*∠(a-y) + (-1/1)*∠(p-y) = 0
- eqangle(b,r,b,y,p,r,p,y): (-1/1)*∠(b-r) + (1/1)*∠(b-y) + (1/1)*∠(p-r) + (-1/1)*∠(p-y) = 0

Assertions:
- eqangle(a,r,p,r,b,y,a,y): (-1/1)*∠(a-r) + (-1/1)*∠(a-y) + (1/1)*∠(b-y) + (1/1)*∠(p-r) = 0

### D133 `dd:r63`

Dependencies: D131, D132, D009

Assumptions:
- eqratio(a,r,a,y,p,r,b,y)
- eqangle(a,r,p,r,b,y,a,y)
- sameclock(a,y,b,a,p,r)

Assertions:
- simtrir(a,b,y,a,p,r)

### D134 `dd:r53`

Dependencies: D133, D009

Assumptions:
- simtrir(a,b,y,a,p,r)
- sameclock(a,y,b,a,p,r)

Assertions:
- eqratio(a,b,a,p,a,y,a,r)

### D135 `dd:r63`

Dependencies: D134, D079, D011

Assumptions:
- eqratio(a,b,a,p,a,y,a,r)
- eqangle(a,b,a,p,a,r,a,y)
- sameclock(b,a,p,y,r,a)

Assertions:
- simtrir(a,b,p,a,y,r)

### D136 `dd:r53`

Dependencies: D135, D010

Assumptions:
- simtrir(a,b,p,a,y,r)
- sameclock(p,b,a,r,a,y)

Assertions:
- eqratio(a,b,a,y,b,p,r,y)

### D137 `ar:angle chasing:directed_angle`

Dependencies: D042, D044, D046, D050, D051, D055, D080, D081, D100, D101, D118

Assumptions:
- para(a,r,b,r): (1/1)*∠(a-r) + (-1/1)*∠(b-r) = 0
- para(b,p,c,p): (1/1)*∠(b-p) + (-1/1)*∠(c-p) = 0
- para(a,q,c,q): (1/1)*∠(a-q) + (-1/1)*∠(c-q) = 0
- para(a,y,p,y): (1/1)*∠(a-y) + (-1/1)*∠(p-y) = 0
- para(a,p,a,y): (1/1)*∠(a-p) + (-1/1)*∠(a-y) = 0
- para(a,p,p,z): (1/1)*∠(a-p) + (-1/1)*∠(p-z) = 0
- eqangle(a,r,a,x,q,r,q,x): (-1/1)*∠(a-r) + (1/1)*∠(a-x) + (1/1)*∠(q-r) + (-1/1)*∠(q-x) = 0
- eqangle(a,q,a,x,q,r,r,x): (-1/1)*∠(a-q) + (1/1)*∠(a-x) + (1/1)*∠(q-r) + (-1/1)*∠(r-x) = 0
- eqangle(c,q,c,z,p,q,p,z): (-1/1)*∠(c-q) + (1/1)*∠(c-z) + (1/1)*∠(p-q) + (-1/1)*∠(p-z) = 0
- eqangle(c,p,c,z,p,q,q,z): (-1/1)*∠(c-p) + (1/1)*∠(c-z) + (1/1)*∠(p-q) + (-1/1)*∠(q-z) = 0
- eqangle(b,p,p,y,b,r,r,y): (-1/1)*∠(b-p) + (1/1)*∠(b-r) + (1/1)*∠(p-y) + (-1/1)*∠(r-y) = 0

Assertions:
- eqangle(q,x,q,z,r,x,r,y): (-1/1)*∠(q-x) + (1/1)*∠(q-z) + (1/1)*∠(r-x) + (-1/1)*∠(r-y) = 0

### D138 `internal_theorem`

Dependencies: D137

Assumptions:
- eqangle(q,x,q,z,r,x,r,y)

Assertions:
- equation_class Yuclid::SinOrDist(x,q,z,x,r,y)

### D139 `ar:ratio chasing:sine_squared+squared_distance` [SINE-DISTANCE BRIDGE]

Dependencies: D070, D072, D074, D083, D085, D087, D089, D091, D093, D095, D097, D099, D102, D104, D106, D108, D110, D112, D114, D116, D120, D121, D122, D123, D125, D127, D128, D129, D130, D134, D136, D138

Assumptions:
- equation_class Yuclid::SinOrDist(a,q,r,c,q,r): (1/1)*\sin² ∠(a q r) + (-1/1)*\sin² ∠(c q r) = 0
- equation_class Yuclid::SinOrDist(c,a,p,p,a,q): (1/1)*\sin² ∠(c a p) + (-1/1)*\sin² ∠(p a q) = 0
- equation_class Yuclid::SinOrDist(p,a,q,q,a,z): (1/1)*\sin² ∠(p a q) + (-1/1)*\sin² ∠(q a z) = 0
- equation_class Yuclid::SinOrDist(a,c,b,a,c,p): (1/1)*\sin² ∠(a c b) + (-1/1)*\sin² ∠(a c p) = 0
- equation_class Yuclid::SinOrDist(a,q,p,c,q,p): (1/1)*\sin² ∠(a q p) + (-1/1)*\sin² ∠(c q p) = 0
- equation_class Yuclid::SinOrDist(a,z,c,c,z,y): (1/1)*\sin² ∠(a z c) + (-1/1)*\sin² ∠(c z y) = 0
- equation_class Yuclid::SinOrDist(c,z,x,c,z,y): (1/1)*\sin² ∠(c z x) + (-1/1)*\sin² ∠(c z y) = 0
- equation_class Yuclid::SinOrDist(a,p,b,b,p,z): (1/1)*\sin² ∠(a p b) + (-1/1)*\sin² ∠(b p z) = 0
- equation_class Yuclid::SinOrDist(b,p,z,c,p,x): (1/1)*\sin² ∠(b p z) + (-1/1)*\sin² ∠(c p x) = 0
- equation_class Yuclid::SinOrDist(a,q,z,c,q,z): (1/1)*\sin² ∠(a q z) + (-1/1)*\sin² ∠(c q z) = 0
- equation_class Yuclid::SinOrDist(a,b,c,a,b,p): (1/1)*\sin² ∠(a b c) + (-1/1)*\sin² ∠(a b p) = 0
- equation_class Yuclid::SinOrDist(a,c,z,q,c,z): (1/1)*\sin² ∠(a c z) + (-1/1)*\sin² ∠(q c z) = 0
- equation_class Yuclid::SinOrDist(q,c,z,q,p,z): (1/1)*\sin² ∠(q c z) + (-1/1)*\sin² ∠(q p z) = 0
- equation_class Yuclid::SinOrDist(a,p,q,q,p,x): (1/1)*\sin² ∠(a p q) + (-1/1)*\sin² ∠(q p x) = 0
- equation_class Yuclid::SinOrDist(q,p,x,q,p,z): (1/1)*\sin² ∠(q p x) + (-1/1)*\sin² ∠(q p z) = 0
- equation_class Yuclid::SinOrDist(a,r,q,b,r,q): (1/1)*\sin² ∠(a r q) + (-1/1)*\sin² ∠(b r q) = 0
- equation_class Yuclid::SinOrDist(b,r,q,q,x,z): (1/1)*\sin² ∠(b r q) + (-1/1)*\sin² ∠(q x z) = 0
- equation_class Yuclid::SinOrDist(c,p,x,c,q,z): (1/1)*\sin² ∠(c p x) + (-1/1)*\sin² ∠(c q z) = 0
- equation_class Yuclid::SinOrDist(c,q,p,c,z,x): (1/1)*\sin² ∠(c q p) + (-1/1)*\sin² ∠(c z x) = 0
- equation_class Yuclid::SinOrDist(c,q,r,r,x,y): (1/1)*\sin² ∠(c q r) + (-1/1)*\sin² ∠(r x y) = 0
- equation_class Yuclid::SinOrDist(a,b,c,a,c,b,a,b,a,c): (1/1)*\sin² ∠(a b c) + (-1/1)*\sin² ∠(a c b) + (1/1)*|a-b|^2 + (-1/1)*|a-c|^2 = 0
- equation_class Yuclid::SinOrDist(a,b,p,a,p,b,a,b,a,p): (1/1)*\sin² ∠(a b p) + (-1/1)*\sin² ∠(a p b) + (1/1)*|a-b|^2 + (-1/1)*|a-p|^2 = 0
- equation_class Yuclid::SinOrDist(a,c,p,c,a,p,a,p,c,p): (1/1)*\sin² ∠(a c p) + (-1/1)*\sin² ∠(c a p) + (-1/1)*|a-p|^2 + (1/1)*|c-p|^2 = 0
- equation_class Yuclid::SinOrDist(a,p,q,a,q,p,a,p,a,q): (1/1)*\sin² ∠(a p q) + (-1/1)*\sin² ∠(a q p) + (1/1)*|a-p|^2 + (-1/1)*|a-q|^2 = 0
- equation_class Yuclid::SinOrDist(a,q,r,a,r,q,a,q,a,r): (1/1)*\sin² ∠(a q r) + (-1/1)*\sin² ∠(a r q) + (1/1)*|a-q|^2 + (-1/1)*|a-r|^2 = 0
- equation_class Yuclid::SinOrDist(r,x,y,x,r,y,r,y,x,y): (1/1)*\sin² ∠(r x y) + (-1/1)*\sin² ∠(x r y) + (-1/1)*|r-y|^2 + (1/1)*|x-y|^2 = 0
- equation_class Yuclid::SinOrDist(a,c,z,a,z,c,a,c,a,z): (1/1)*\sin² ∠(a c z) + (-1/1)*\sin² ∠(a z c) + (1/1)*|a-c|^2 + (-1/1)*|a-z|^2 = 0
- equation_class Yuclid::SinOrDist(a,q,z,q,a,z,a,z,q,z): (1/1)*\sin² ∠(a q z) + (-1/1)*\sin² ∠(q a z) + (-1/1)*|a-z|^2 + (1/1)*|q-z|^2 = 0
- equation_class Yuclid::SinOrDist(q,x,z,x,q,z,q,z,x,z): (1/1)*\sin² ∠(q x z) + (-1/1)*\sin² ∠(x q z) + (-1/1)*|q-z|^2 + (1/1)*|x-z|^2 = 0
- eqratio(a,b,a,p,a,y,a,r): (1/1)*|a-b|^2 + (-1/1)*|a-p|^2 + (1/1)*|a-r|^2 + (-1/1)*|a-y|^2 = 0
- eqratio(a,b,a,y,b,p,r,y): (1/1)*|a-b|^2 + (-1/1)*|a-y|^2 + (-1/1)*|b-p|^2 + (1/1)*|r-y|^2 = 0
- equation_class Yuclid::SinOrDist(x,q,z,x,r,y): (1/1)*\sin² ∠(x q z) + (-1/1)*\sin² ∠(x r y) = 0

Assertions:
- eqratio(b,p,c,p,x,y,x,z): (1/1)*|b-p|^2 + (-1/1)*|c-p|^2 + (-1/1)*|x-y|^2 + (1/1)*|x-z|^2 = 0
