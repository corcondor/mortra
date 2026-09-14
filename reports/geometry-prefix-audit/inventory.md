# Geometry execution inventory

This is an aggregation of saved events, not a new solve.
Counts are event occurrences. A success is an executed construction with primitive replay, not a solved task.
Failed predicate requests cannot be reconstructed when the original trace omitted them.

## diagnostic:A

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 528 | 512 | 462 | 50 |
| mirror | primitive | 528 | 512 | 450 | 62 |
| foot | primitive | 528 | 512 | 330 | 182 |
| circle | primitive | 528 | 512 | 482 | 30 |
| orthocenter | primitive | 528 | 512 | 378 | 134 |
| reflect | primitive | 528 | 512 | 354 | 158 |
| intersection_ll | primitive | 528 | 512 | 306 | 206 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.a6b900e0f674d6cf1e9c | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.95e24700e08df3c4585e | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.6a9edceaf4c1c846e632 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.1b84f7c7e765b803d0dd | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.299996baaf4fc2f00a1f | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.637fe8db3854c7bf2f58 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.13e1670a636cac7a3706 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.200fecc1e1b0b85fe0f0 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.d33abd09088679bd0193 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.84ef8b9e4166008b3828 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.7af21c2e953bcbb21998 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.86730dfc0826455cea3a | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.aced3b76e3d056c8aadb | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.68fd5c2cd6907789ee4d | acquired | 0 | 0 | 0 | 0 |

Consumed premises in successful constructions:
```json
{
  "diff": 684,
  "ncoll": 860,
  "npara": 306
}
```

## diagnostic:D

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 168 | 154 | 134 | 20 |
| mirror | primitive | 168 | 154 | 138 | 16 |
| foot | primitive | 168 | 158 | 102 | 56 |
| circle | primitive | 168 | 154 | 139 | 15 |
| orthocenter | primitive | 168 | 154 | 119 | 35 |
| reflect | primitive | 168 | 158 | 116 | 42 |
| intersection_ll | primitive | 168 | 158 | 88 | 70 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 168 | 154 | 40 | 114 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 168 | 156 | 44 | 112 |
| geom.semantic.a6b900e0f674d6cf1e9c | acquired | 168 | 160 | 56 | 104 |
| geom.semantic.95e24700e08df3c4585e | acquired | 168 | 158 | 62 | 96 |
| geom.semantic.6a9edceaf4c1c846e632 | acquired | 168 | 154 | 120 | 34 |
| geom.semantic.1b84f7c7e765b803d0dd | acquired | 168 | 158 | 116 | 42 |
| geom.semantic.299996baaf4fc2f00a1f | acquired | 168 | 156 | 44 | 112 |
| geom.semantic.637fe8db3854c7bf2f58 | acquired | 168 | 154 | 134 | 20 |
| geom.semantic.13e1670a636cac7a3706 | acquired | 168 | 152 | 124 | 28 |
| geom.semantic.200fecc1e1b0b85fe0f0 | acquired | 168 | 154 | 142 | 12 |
| geom.semantic.d33abd09088679bd0193 | acquired | 168 | 152 | 104 | 48 |
| geom.semantic.84ef8b9e4166008b3828 | acquired | 168 | 158 | 62 | 96 |
| geom.semantic.7af21c2e953bcbb21998 | acquired | 168 | 158 | 142 | 16 |
| geom.semantic.86730dfc0826455cea3a | acquired | 168 | 156 | 146 | 10 |
| geom.semantic.aced3b76e3d056c8aadb | acquired | 168 | 156 | 46 | 110 |
| geom.semantic.68fd5c2cd6907789ee4d | acquired | 168 | 158 | 132 | 26 |

Consumed premises in successful constructions:
```json
{
  "npara": 88,
  "diff": 218,
  "ncoll": 258
}
```

## regression:A

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 168 | 136 | 120 | 16 |
| mirror | primitive | 162 | 134 | 114 | 20 |
| foot | primitive | 162 | 134 | 84 | 50 |
| circle | primitive | 156 | 132 | 122 | 10 |
| orthocenter | primitive | 150 | 130 | 102 | 28 |
| reflect | primitive | 144 | 128 | 96 | 32 |
| intersection_ll | primitive | 144 | 128 | 80 | 48 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.a6b900e0f674d6cf1e9c | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.95e24700e08df3c4585e | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.6a9edceaf4c1c846e632 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.1b84f7c7e765b803d0dd | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.299996baaf4fc2f00a1f | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.637fe8db3854c7bf2f58 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.13e1670a636cac7a3706 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.200fecc1e1b0b85fe0f0 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.d33abd09088679bd0193 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.84ef8b9e4166008b3828 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.7af21c2e953bcbb21998 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.86730dfc0826455cea3a | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.aced3b76e3d056c8aadb | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.68fd5c2cd6907789ee4d | acquired | 0 | 0 | 0 | 0 |

Consumed premises in successful constructions:
```json
{
  "diff": 180,
  "ncoll": 224,
  "npara": 80
}
```

## regression:B

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 168 | 130 | 114 | 16 |
| mirror | primitive | 168 | 128 | 108 | 20 |
| foot | primitive | 168 | 130 | 80 | 50 |
| circle | primitive | 168 | 130 | 126 | 4 |
| orthocenter | primitive | 168 | 130 | 108 | 22 |
| reflect | primitive | 168 | 128 | 80 | 48 |
| intersection_ll | primitive | 168 | 128 | 72 | 56 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.a6b900e0f674d6cf1e9c | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.95e24700e08df3c4585e | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.6a9edceaf4c1c846e632 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.1b84f7c7e765b803d0dd | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.299996baaf4fc2f00a1f | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.637fe8db3854c7bf2f58 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.13e1670a636cac7a3706 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.200fecc1e1b0b85fe0f0 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.d33abd09088679bd0193 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.84ef8b9e4166008b3828 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.7af21c2e953bcbb21998 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.86730dfc0826455cea3a | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.aced3b76e3d056c8aadb | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.68fd5c2cd6907789ee4d | acquired | 0 | 0 | 0 | 0 |

Consumed premises in successful constructions:
```json
{
  "diff": 160,
  "ncoll": 234,
  "npara": 72
}
```

## regression:C

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 72 | 48 | 48 | 0 |
| mirror | primitive | 66 | 46 | 38 | 8 |
| foot | primitive | 66 | 46 | 28 | 18 |
| circle | primitive | 60 | 44 | 44 | 0 |
| orthocenter | primitive | 54 | 42 | 40 | 2 |
| reflect | primitive | 48 | 40 | 24 | 16 |
| intersection_ll | primitive | 48 | 40 | 24 | 16 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 48 | 40 | 0 | 40 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 48 | 40 | 0 | 40 |
| geom.semantic.a6b900e0f674d6cf1e9c | acquired | 48 | 40 | 0 | 40 |
| geom.semantic.95e24700e08df3c4585e | acquired | 48 | 40 | 0 | 40 |
| geom.semantic.6a9edceaf4c1c846e632 | acquired | 48 | 40 | 36 | 4 |
| geom.semantic.1b84f7c7e765b803d0dd | acquired | 48 | 40 | 36 | 4 |
| geom.semantic.299996baaf4fc2f00a1f | acquired | 48 | 40 | 0 | 40 |
| geom.semantic.637fe8db3854c7bf2f58 | acquired | 48 | 40 | 38 | 2 |
| geom.semantic.13e1670a636cac7a3706 | acquired | 48 | 40 | 36 | 4 |
| geom.semantic.200fecc1e1b0b85fe0f0 | acquired | 48 | 40 | 40 | 0 |
| geom.semantic.d33abd09088679bd0193 | acquired | 48 | 40 | 32 | 8 |
| geom.semantic.84ef8b9e4166008b3828 | acquired | 48 | 40 | 0 | 40 |
| geom.semantic.7af21c2e953bcbb21998 | acquired | 48 | 40 | 38 | 2 |
| geom.semantic.86730dfc0826455cea3a | acquired | 48 | 32 | 30 | 2 |
| geom.semantic.aced3b76e3d056c8aadb | acquired | 48 | 32 | 0 | 32 |
| geom.semantic.68fd5c2cd6907789ee4d | acquired | 48 | 32 | 16 | 16 |

Consumed premises in successful constructions:
```json
{
  "diff": 52,
  "ncoll": 84,
  "npara": 24
}
```

## regression:D

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 72 | 42 | 38 | 4 |
| mirror | primitive | 72 | 38 | 38 | 0 |
| foot | primitive | 72 | 42 | 34 | 8 |
| circle | primitive | 72 | 40 | 36 | 4 |
| orthocenter | primitive | 72 | 38 | 32 | 6 |
| reflect | primitive | 72 | 40 | 36 | 4 |
| intersection_ll | primitive | 72 | 40 | 34 | 6 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 72 | 38 | 6 | 32 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 72 | 40 | 6 | 34 |
| geom.semantic.a6b900e0f674d6cf1e9c | acquired | 72 | 40 | 8 | 32 |
| geom.semantic.95e24700e08df3c4585e | acquired | 72 | 40 | 10 | 30 |
| geom.semantic.6a9edceaf4c1c846e632 | acquired | 72 | 38 | 30 | 8 |
| geom.semantic.1b84f7c7e765b803d0dd | acquired | 72 | 38 | 32 | 6 |
| geom.semantic.299996baaf4fc2f00a1f | acquired | 72 | 40 | 4 | 36 |
| geom.semantic.637fe8db3854c7bf2f58 | acquired | 72 | 40 | 38 | 2 |
| geom.semantic.13e1670a636cac7a3706 | acquired | 72 | 36 | 28 | 8 |
| geom.semantic.200fecc1e1b0b85fe0f0 | acquired | 72 | 40 | 38 | 2 |
| geom.semantic.d33abd09088679bd0193 | acquired | 72 | 36 | 28 | 8 |
| geom.semantic.84ef8b9e4166008b3828 | acquired | 72 | 40 | 12 | 28 |
| geom.semantic.7af21c2e953bcbb21998 | acquired | 72 | 40 | 36 | 4 |
| geom.semantic.86730dfc0826455cea3a | acquired | 72 | 40 | 38 | 2 |
| geom.semantic.aced3b76e3d056c8aadb | acquired | 72 | 38 | 8 | 30 |
| geom.semantic.68fd5c2cd6907789ee4d | acquired | 72 | 40 | 30 | 10 |

Consumed premises in successful constructions:
```json
{
  "diff": 70,
  "ncoll": 68,
  "npara": 34
}
```

## transfer:A

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 168 | 136 | 120 | 16 |
| mirror | primitive | 162 | 134 | 114 | 20 |
| foot | primitive | 162 | 134 | 86 | 48 |
| circle | primitive | 156 | 132 | 124 | 8 |
| orthocenter | primitive | 150 | 130 | 106 | 24 |
| reflect | primitive | 144 | 128 | 96 | 32 |
| intersection_ll | primitive | 144 | 128 | 79 | 49 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.a6b900e0f674d6cf1e9c | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.95e24700e08df3c4585e | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.6a9edceaf4c1c846e632 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.1b84f7c7e765b803d0dd | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.299996baaf4fc2f00a1f | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.637fe8db3854c7bf2f58 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.13e1670a636cac7a3706 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.200fecc1e1b0b85fe0f0 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.d33abd09088679bd0193 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.84ef8b9e4166008b3828 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.7af21c2e953bcbb21998 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.86730dfc0826455cea3a | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.aced3b76e3d056c8aadb | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.68fd5c2cd6907789ee4d | acquired | 0 | 0 | 0 | 0 |

Consumed premises in successful constructions:
```json
{
  "diff": 182,
  "ncoll": 230,
  "npara": 79
}
```

## transfer:B

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 168 | 130 | 113 | 17 |
| mirror | primitive | 168 | 128 | 108 | 20 |
| foot | primitive | 168 | 130 | 82 | 48 |
| circle | primitive | 168 | 130 | 128 | 2 |
| orthocenter | primitive | 168 | 130 | 112 | 18 |
| reflect | primitive | 168 | 128 | 80 | 48 |
| intersection_ll | primitive | 166 | 128 | 71 | 57 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.a6b900e0f674d6cf1e9c | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.95e24700e08df3c4585e | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.6a9edceaf4c1c846e632 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.1b84f7c7e765b803d0dd | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.299996baaf4fc2f00a1f | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.637fe8db3854c7bf2f58 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.13e1670a636cac7a3706 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.200fecc1e1b0b85fe0f0 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.d33abd09088679bd0193 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.84ef8b9e4166008b3828 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.7af21c2e953bcbb21998 | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.86730dfc0826455cea3a | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.aced3b76e3d056c8aadb | acquired | 0 | 0 | 0 | 0 |
| geom.semantic.68fd5c2cd6907789ee4d | acquired | 0 | 0 | 0 | 0 |

Consumed premises in successful constructions:
```json
{
  "diff": 162,
  "ncoll": 240,
  "npara": 71
}
```

## transfer:C

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 72 | 48 | 48 | 0 |
| mirror | primitive | 66 | 46 | 38 | 8 |
| foot | primitive | 66 | 46 | 30 | 16 |
| circle | primitive | 60 | 44 | 44 | 0 |
| orthocenter | primitive | 54 | 42 | 42 | 0 |
| reflect | primitive | 48 | 40 | 24 | 16 |
| intersection_ll | primitive | 48 | 40 | 24 | 16 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 48 | 40 | 0 | 40 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 48 | 40 | 0 | 40 |
| geom.semantic.a6b900e0f674d6cf1e9c | acquired | 48 | 40 | 0 | 40 |
| geom.semantic.95e24700e08df3c4585e | acquired | 48 | 40 | 0 | 40 |
| geom.semantic.6a9edceaf4c1c846e632 | acquired | 48 | 40 | 36 | 4 |
| geom.semantic.1b84f7c7e765b803d0dd | acquired | 48 | 40 | 36 | 4 |
| geom.semantic.299996baaf4fc2f00a1f | acquired | 48 | 40 | 0 | 40 |
| geom.semantic.637fe8db3854c7bf2f58 | acquired | 48 | 40 | 40 | 0 |
| geom.semantic.13e1670a636cac7a3706 | acquired | 48 | 40 | 36 | 4 |
| geom.semantic.200fecc1e1b0b85fe0f0 | acquired | 48 | 40 | 40 | 0 |
| geom.semantic.d33abd09088679bd0193 | acquired | 48 | 40 | 32 | 8 |
| geom.semantic.84ef8b9e4166008b3828 | acquired | 48 | 40 | 0 | 40 |
| geom.semantic.7af21c2e953bcbb21998 | acquired | 48 | 40 | 40 | 0 |
| geom.semantic.86730dfc0826455cea3a | acquired | 48 | 32 | 32 | 0 |
| geom.semantic.aced3b76e3d056c8aadb | acquired | 48 | 32 | 0 | 32 |
| geom.semantic.68fd5c2cd6907789ee4d | acquired | 48 | 32 | 16 | 16 |

Consumed premises in successful constructions:
```json
{
  "diff": 54,
  "ncoll": 86,
  "npara": 24
}
```

## transfer:D

| Operation | Kind | Proposed | Selected | Successful | Refused |
|---|---|---:|---:|---:|---:|
| midpoint | primitive | 72 | 42 | 38 | 4 |
| mirror | primitive | 72 | 38 | 38 | 0 |
| foot | primitive | 72 | 42 | 36 | 6 |
| circle | primitive | 72 | 40 | 36 | 4 |
| orthocenter | primitive | 72 | 38 | 34 | 4 |
| reflect | primitive | 72 | 40 | 36 | 4 |
| intersection_ll | primitive | 70 | 40 | 34 | 6 |
| geom.semantic.4ccca6d87a48ddbf708e | acquired | 72 | 38 | 6 | 32 |
| geom.semantic.05d17c37a0a51f7143a4 | acquired | 72 | 40 | 6 | 34 |
| geom.semantic.a6b900e0f674d6cf1e9c | acquired | 72 | 40 | 8 | 32 |
| geom.semantic.95e24700e08df3c4585e | acquired | 72 | 40 | 10 | 30 |
| geom.semantic.6a9edceaf4c1c846e632 | acquired | 72 | 38 | 30 | 8 |
| geom.semantic.1b84f7c7e765b803d0dd | acquired | 72 | 38 | 32 | 6 |
| geom.semantic.299996baaf4fc2f00a1f | acquired | 72 | 40 | 4 | 36 |
| geom.semantic.637fe8db3854c7bf2f58 | acquired | 72 | 40 | 40 | 0 |
| geom.semantic.13e1670a636cac7a3706 | acquired | 72 | 36 | 28 | 8 |
| geom.semantic.200fecc1e1b0b85fe0f0 | acquired | 72 | 40 | 38 | 2 |
| geom.semantic.d33abd09088679bd0193 | acquired | 72 | 36 | 28 | 8 |
| geom.semantic.84ef8b9e4166008b3828 | acquired | 72 | 40 | 12 | 28 |
| geom.semantic.7af21c2e953bcbb21998 | acquired | 72 | 40 | 38 | 2 |
| geom.semantic.86730dfc0826455cea3a | acquired | 72 | 40 | 40 | 0 |
| geom.semantic.aced3b76e3d056c8aadb | acquired | 72 | 38 | 8 | 30 |
| geom.semantic.68fd5c2cd6907789ee4d | acquired | 72 | 40 | 30 | 10 |

Consumed premises in successful constructions:
```json
{
  "diff": 72,
  "ncoll": 70,
  "npara": 34
}
```
