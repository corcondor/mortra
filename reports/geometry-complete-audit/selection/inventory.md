# Geometry execution inventory

This is an aggregation of saved events, not a new solve.
Counts are event occurrences. A success is an executed construction with primitive replay, not a solved task.
Failed predicate requests cannot be reconstructed when the original trace omitted them.

## diagnostic:A

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 5988 | 512 | 408 | 104 |
| mirror | primitive | 7008 | 512 | 406 | 106 |
| foot | primitive | 7008 | 512 | 392 | 120 |
| circle | primitive | 6182 | 512 | 408 | 104 |
| orthocenter | primitive | 6182 | 512 | 398 | 114 |
| reflect | primitive | 7008 | 512 | 412 | 100 |
| intersection_ll | primitive | 6814 | 512 | 420 | 92 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.e3938bd5fb6099969c43 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.044b9fe6707b8dd0eaf4 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.19a2d7cfd1a968043ceb | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.212ca5f01960f998b958 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.4a08d8465682159ce9ab | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.fbdfaf9c61448fba6df2 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.ef3a96e0d48973ebdf19 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.74fa2a03a824a445a6f6 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.d73c2890f308cc06f742 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.6fa3c8b0fc421e9492d6 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.3347a41193f4041b39cd | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.cf787a1ef31e449ab8c9 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.2f596a950596ccf09134 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.e03c313e1b27e5828723 | acquired | 0 | 0 | 0 | 0 |

Consumed premises in successful constructions:
```json
{
  "diff": 804,
  "ncoll": 806,
  "npara": 420
}
```

## diagnostic:D

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 10564 | 266 | 226 | 40 |
| mirror | primitive | 11776 | 88 | 80 | 8 |
| foot | primitive | 11776 | 108 | 98 | 10 |
| circle | primitive | 10788 | 266 | 228 | 38 |
| orthocenter | primitive | 10788 | 256 | 202 | 54 |
| reflect | primitive | 11776 | 108 | 100 | 8 |
| intersection_ll | primitive | 11560 | 88 | 80 | 8 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 11808 | 88 | 2 | 86 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 11808 | 88 | 0 | 88 |
| geom.semantic.e3938bd5fb6099969c43 | acquired | 11808 | 302 | 0 | 302 |
| geom.semantic.044b9fe6707b8dd0eaf4 | acquired | 11808 | 88 | 0 | 88 |
| geom.semantic.19a2d7cfd1a968043ceb | acquired | 11808 | 88 | 0 | 88 |
| geom.semantic.212ca5f01960f998b958 | acquired | 11808 | 300 | 64 | 236 |
| geom.semantic.4a08d8465682159ce9ab | acquired | 11808 | 198 | 2 | 196 |
| geom.semantic.fbdfaf9c61448fba6df2 | acquired | 11808 | 300 | 0 | 300 |
| geom.semantic.ef3a96e0d48973ebdf19 | acquired | 11808 | 92 | 0 | 92 |
| geom.semantic.74fa2a03a824a445a6f6 | acquired | 11808 | 88 | 0 | 88 |
| geom.semantic.d73c2890f308cc06f742 | acquired | 11808 | 122 | 2 | 120 |
| geom.semantic.6fa3c8b0fc421e9492d6 | acquired | 11808 | 88 | 0 | 88 |
| geom.semantic.3347a41193f4041b39cd | acquired | 11808 | 88 | 8 | 80 |
| geom.semantic.cf787a1ef31e449ab8c9 | acquired | 11808 | 298 | 62 | 236 |
| geom.semantic.2f596a950596ccf09134 | acquired | 11808 | 88 | 78 | 10 |
| geom.semantic.e03c313e1b27e5828723 | acquired | 11808 | 88 | 78 | 10 |

Consumed premises in successful constructions:
```json
{
  "diff": 198,
  "npara": 80,
  "ncoll": 430
}
```

## regression:A

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 756 | 148 | 138 | 10 |
| mirror | primitive | 1224 | 146 | 136 | 10 |
| foot | primitive | 1224 | 146 | 122 | 24 |
| circle | primitive | 670 | 146 | 136 | 10 |
| orthocenter | primitive | 662 | 144 | 120 | 24 |
| reflect | primitive | 1176 | 142 | 132 | 10 |
| intersection_ll | primitive | 1012 | 142 | 128 | 14 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.e3938bd5fb6099969c43 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.044b9fe6707b8dd0eaf4 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.19a2d7cfd1a968043ceb | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.212ca5f01960f998b958 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.4a08d8465682159ce9ab | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.fbdfaf9c61448fba6df2 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.ef3a96e0d48973ebdf19 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.74fa2a03a824a445a6f6 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.d73c2890f308cc06f742 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.6fa3c8b0fc421e9492d6 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.3347a41193f4041b39cd | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.cf787a1ef31e449ab8c9 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.2f596a950596ccf09134 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.e03c313e1b27e5828723 | acquired | 0 | 0 | 0 | 0 |

Consumed premises in successful constructions:
```json
{
  "diff": 254,
  "ncoll": 256,
  "npara": 128
}
```

## regression:B

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 6246 | 368 | 290 | 78 |
| mirror | primitive | 7328 | 72 | 64 | 8 |
| foot | primitive | 7328 | 80 | 70 | 10 |
| circle | primitive | 6430 | 74 | 68 | 6 |
| orthocenter | primitive | 6430 | 152 | 120 | 32 |
| reflect | primitive | 7328 | 86 | 78 | 8 |
| intersection_ll | primitive | 7062 | 72 | 64 | 8 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.e3938bd5fb6099969c43 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.044b9fe6707b8dd0eaf4 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.19a2d7cfd1a968043ceb | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.212ca5f01960f998b958 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.4a08d8465682159ce9ab | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.fbdfaf9c61448fba6df2 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.ef3a96e0d48973ebdf19 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.74fa2a03a824a445a6f6 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.d73c2890f308cc06f742 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.6fa3c8b0fc421e9492d6 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.3347a41193f4041b39cd | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.cf787a1ef31e449ab8c9 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.2f596a950596ccf09134 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.e03c313e1b27e5828723 | acquired | 0 | 0 | 0 | 0 |

Consumed premises in successful constructions:
```json
{
  "diff": 148,
  "ncoll": 188,
  "npara": 64
}
```

## regression:C

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 396 | 56 | 46 | 10 |
| mirror | primitive | 648 | 54 | 44 | 10 |
| foot | primitive | 648 | 54 | 42 | 12 |
| circle | primitive | 326 | 54 | 54 | 0 |
| orthocenter | primitive | 318 | 52 | 50 | 2 |
| reflect | primitive | 600 | 50 | 50 | 0 |
| intersection_ll | primitive | 478 | 50 | 44 | 6 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.e3938bd5fb6099969c43 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.044b9fe6707b8dd0eaf4 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.19a2d7cfd1a968043ceb | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.212ca5f01960f998b958 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.4a08d8465682159ce9ab | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.fbdfaf9c61448fba6df2 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.ef3a96e0d48973ebdf19 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.74fa2a03a824a445a6f6 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.d73c2890f308cc06f742 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.6fa3c8b0fc421e9492d6 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.3347a41193f4041b39cd | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.cf787a1ef31e449ab8c9 | acquired | 480 | 40 | 0 | 40 |
| geom.semantic.2f596a950596ccf09134 | acquired | 480 | 40 | 10 | 30 |
| geom.semantic.e03c313e1b27e5828723 | acquired | 480 | 40 | 10 | 30 |

Consumed premises in successful constructions:
```json
{
  "diff": 92,
  "ncoll": 104,
  "npara": 44
}
```

## regression:D

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 896 | 86 | 78 | 8 |
| mirror | primitive | 1344 | 52 | 48 | 4 |
| foot | primitive | 1344 | 58 | 51 | 7 |
| circle | primitive | 840 | 42 | 40 | 2 |
| orthocenter | primitive | 840 | 28 | 26 | 2 |
| reflect | primitive | 1344 | 38 | 34 | 4 |
| intersection_ll | primitive | 1138 | 44 | 40 | 4 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 1408 | 8 | 0 | 8 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 1408 | 8 | 0 | 8 |
| geom.semantic.e3938bd5fb6099969c43 | acquired | 1408 | 68 | 0 | 68 |
| geom.semantic.044b9fe6707b8dd0eaf4 | acquired | 1408 | 30 | 0 | 30 |
| geom.semantic.19a2d7cfd1a968043ceb | acquired | 1408 | 8 | 0 | 8 |
| geom.semantic.212ca5f01960f998b958 | acquired | 1408 | 68 | 6 | 62 |
| geom.semantic.4a08d8465682159ce9ab | acquired | 1408 | 68 | 0 | 68 |
| geom.semantic.fbdfaf9c61448fba6df2 | acquired | 1408 | 68 | 0 | 68 |
| geom.semantic.ef3a96e0d48973ebdf19 | acquired | 1408 | 14 | 0 | 14 |
| geom.semantic.74fa2a03a824a445a6f6 | acquired | 1408 | 8 | 0 | 8 |
| geom.semantic.d73c2890f308cc06f742 | acquired | 1408 | 48 | 0 | 48 |
| geom.semantic.6fa3c8b0fc421e9492d6 | acquired | 1408 | 28 | 0 | 28 |
| geom.semantic.3347a41193f4041b39cd | acquired | 1408 | 28 | 2 | 26 |
| geom.semantic.cf787a1ef31e449ab8c9 | acquired | 1408 | 68 | 6 | 62 |
| geom.semantic.2f596a950596ccf09134 | acquired | 1408 | 28 | 25 | 3 |
| geom.semantic.e03c313e1b27e5828723 | acquired | 1408 | 8 | 8 | 0 |

Consumed premises in successful constructions:
```json
{
  "diff": 85,
  "ncoll": 66,
  "npara": 40
}
```

## transfer:A

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 756 | 148 | 138 | 10 |
| mirror | primitive | 1224 | 146 | 136 | 10 |
| foot | primitive | 1224 | 146 | 135 | 11 |
| circle | primitive | 670 | 146 | 136 | 10 |
| orthocenter | primitive | 662 | 144 | 133 | 11 |
| reflect | primitive | 1176 | 142 | 134 | 8 |
| intersection_ll | primitive | 1019 | 142 | 128 | 14 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.e3938bd5fb6099969c43 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.044b9fe6707b8dd0eaf4 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.19a2d7cfd1a968043ceb | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.212ca5f01960f998b958 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.4a08d8465682159ce9ab | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.fbdfaf9c61448fba6df2 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.ef3a96e0d48973ebdf19 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.74fa2a03a824a445a6f6 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.d73c2890f308cc06f742 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.6fa3c8b0fc421e9492d6 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.3347a41193f4041b39cd | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.cf787a1ef31e449ab8c9 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.2f596a950596ccf09134 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.e03c313e1b27e5828723 | acquired | 0 | 0 | 0 | 0 |

Consumed premises in successful constructions:
```json
{
  "diff": 269,
  "ncoll": 269,
  "npara": 128
}
```

## transfer:B

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 6256 | 366 | 288 | 78 |
| mirror | primitive | 7360 | 73 | 64 | 9 |
| foot | primitive | 7360 | 81 | 73 | 8 |
| circle | primitive | 6437 | 74 | 68 | 6 |
| orthocenter | primitive | 6437 | 152 | 122 | 30 |
| reflect | primitive | 7360 | 86 | 78 | 8 |
| intersection_ll | primitive | 7099 | 72 | 63 | 9 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.e3938bd5fb6099969c43 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.044b9fe6707b8dd0eaf4 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.19a2d7cfd1a968043ceb | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.212ca5f01960f998b958 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.4a08d8465682159ce9ab | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.fbdfaf9c61448fba6df2 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.ef3a96e0d48973ebdf19 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.74fa2a03a824a445a6f6 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.d73c2890f308cc06f742 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.6fa3c8b0fc421e9492d6 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.3347a41193f4041b39cd | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.cf787a1ef31e449ab8c9 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.2f596a950596ccf09134 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.e03c313e1b27e5828723 | acquired | 0 | 0 | 0 | 0 |

Consumed premises in successful constructions:
```json
{
  "diff": 151,
  "ncoll": 190,
  "npara": 63
}
```

## transfer:C

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 396 | 56 | 46 | 10 |
| mirror | primitive | 648 | 54 | 44 | 10 |
| foot | primitive | 648 | 54 | 43 | 11 |
| circle | primitive | 326 | 54 | 54 | 0 |
| orthocenter | primitive | 318 | 52 | 51 | 1 |
| reflect | primitive | 600 | 50 | 50 | 0 |
| intersection_ll | primitive | 479 | 50 | 44 | 6 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.e3938bd5fb6099969c43 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.044b9fe6707b8dd0eaf4 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.19a2d7cfd1a968043ceb | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.212ca5f01960f998b958 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.4a08d8465682159ce9ab | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.fbdfaf9c61448fba6df2 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.ef3a96e0d48973ebdf19 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.74fa2a03a824a445a6f6 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.d73c2890f308cc06f742 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.6fa3c8b0fc421e9492d6 | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.3347a41193f4041b39cd | acquired | 640 | 50 | 0 | 50 |
| geom.semantic.cf787a1ef31e449ab8c9 | acquired | 480 | 40 | 0 | 40 |
| geom.semantic.2f596a950596ccf09134 | acquired | 480 | 40 | 10 | 30 |
| geom.semantic.e03c313e1b27e5828723 | acquired | 480 | 40 | 10 | 30 |

Consumed premises in successful constructions:
```json
{
  "diff": 93,
  "ncoll": 105,
  "npara": 44
}
```

## transfer:D

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 896 | 86 | 78 | 8 |
| mirror | primitive | 1344 | 52 | 47 | 5 |
| foot | primitive | 1344 | 58 | 52 | 6 |
| circle | primitive | 839 | 42 | 40 | 2 |
| orthocenter | primitive | 839 | 28 | 26 | 2 |
| reflect | primitive | 1344 | 38 | 34 | 4 |
| intersection_ll | primitive | 1141 | 44 | 39 | 5 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 1408 | 8 | 0 | 8 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 1408 | 8 | 0 | 8 |
| geom.semantic.e3938bd5fb6099969c43 | acquired | 1408 | 68 | 0 | 68 |
| geom.semantic.044b9fe6707b8dd0eaf4 | acquired | 1408 | 30 | 0 | 30 |
| geom.semantic.19a2d7cfd1a968043ceb | acquired | 1408 | 8 | 0 | 8 |
| geom.semantic.212ca5f01960f998b958 | acquired | 1408 | 68 | 6 | 62 |
| geom.semantic.4a08d8465682159ce9ab | acquired | 1408 | 68 | 0 | 68 |
| geom.semantic.fbdfaf9c61448fba6df2 | acquired | 1408 | 68 | 0 | 68 |
| geom.semantic.ef3a96e0d48973ebdf19 | acquired | 1408 | 14 | 0 | 14 |
| geom.semantic.74fa2a03a824a445a6f6 | acquired | 1408 | 8 | 0 | 8 |
| geom.semantic.d73c2890f308cc06f742 | acquired | 1408 | 48 | 0 | 48 |
| geom.semantic.6fa3c8b0fc421e9492d6 | acquired | 1408 | 28 | 0 | 28 |
| geom.semantic.3347a41193f4041b39cd | acquired | 1408 | 28 | 2 | 26 |
| geom.semantic.cf787a1ef31e449ab8c9 | acquired | 1408 | 68 | 6 | 62 |
| geom.semantic.2f596a950596ccf09134 | acquired | 1408 | 28 | 26 | 2 |
| geom.semantic.e03c313e1b27e5828723 | acquired | 1408 | 8 | 8 | 0 |

Consumed premises in successful constructions:
```json
{
  "diff": 86,
  "ncoll": 66,
  "npara": 39
}
```
