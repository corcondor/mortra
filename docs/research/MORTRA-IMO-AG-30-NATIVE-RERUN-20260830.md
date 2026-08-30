# MORTRA IMO-AG-30 native再実行

日付: 2026-08-30

## 目的

過去の集計値を転記せず、現在の実行環境からIMO-AG-30の公式形式化を再実行する。
問題ごとの分岐や外部LLMを使わず、同一の記号推論器と同一条件で30問を評価する。

## 方法

- 問題集合: Newclid `yuclid/test/imo_ag_30` の原問題30問
- Newclid commit: `ac6550732a950564cf7614d605b5bf1eadd29701`
- 実行器SHA-256: `dc40a72767c15a90b48471619a0b00734b611eeecfc9c7815328ae0eae4f1397`
- Python: `3.12.10`
- 推論: Yuclid DDAR、all-AR
- 制限: 1問30秒、500 iteration
- 外部LLM: 不使用
- 補助点生成器: 不使用
- 受理条件: Yuclid native終了コード0と解析可能な証明JSON

原問題の `2019_p2` と、公式READMEで用いられる `2019_p2_easy` は混同せず、別々に集計した。
各実行の標準出力を証明JSONとして保存し、記録されたSHA-256と再計算値を照合した。

## 結果

| 集計 | 正答 | 飽和未解決 | 時間超過 | 異常終了 |
|---|---:|---:|---:|---:|
| 原問題IMO-AG-30 | **17/30** | 13 | 0 | 0 |
| READMEの易化版を含む30問 | **18/30** | 12 | 0 | 0 |

全31実行の壁時計時間は50.92秒だった。証明成果物の監査結果は次の通り。

| 監査 | 結果 |
|---|---:|
| 証明JSONの保存 | 31/31 |
| JSON解析 | 31/31 |
| 証明SHA-256一致 | 31/31 |

成果物:

- `data/yuclid-imo-ag-30-all-ar-2026-08-30.json`
- `artifacts/benchmarks/imo-ag-30-all-ar-2026-08-30-proofs/`

## 考察

この17/30は、同一コマンドだけを全問へ適用したYuclid DDAR単体の再現値である。
複数の補助構成探索、Wu/Groebner証明、型付きチャートを統合したMORTRA portfolioとは
評価単位が異なるため、portfolio値と加算または置換しない。

13問は時間超過ではなく、与えた構成と規則の下で閉包が飽和して停止した。
したがって、この条件で正答を増やすには時間延長ではなく、未解決goalから補助構成または
中間補題を生成し、native証明へ戻す経路の追加が必要である。

## 結論

現在の公式Newclid環境で、外部LLMを使わないIMO-AG-30 native baselineを再現した。
原問題は17/30、公式READMEの易化版を含む定義では18/30であり、全証明成果物の保存、解析、
SHA-256照合に成功した。今後の改善はこの固定成果物を対照群として測る。

## 再現

```powershell
python scripts/reproduce_yuclid_imo_ag_30.py `
  --yuclid-exe C:\Users\81808\.cache\mortra-research-sources\Newclid\.venv\Scripts\yuclid.exe `
  --newclid-root C:\Users\81808\.cache\mortra-research-sources\Newclid `
  --runtime-path C:\Users\81808\.cache\mortra-research-sources\boost_1_88_dlls\app\lib64-msvc-14.3 `
  --ar-profile all `
  --timeout-seconds 30 `
  --proof-dir artifacts\benchmarks\imo-ag-30-all-ar-2026-08-30-proofs `
  --output data\yuclid-imo-ag-30-all-ar-2026-08-30.json
```
