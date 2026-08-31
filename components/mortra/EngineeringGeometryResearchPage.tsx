import Image from 'next/image'
import Link from 'next/link'
import {
  ArrowLeft,
  ArrowRight,
  Box,
  Download,
  FileJson2,
  Github,
  Layers3,
  Ruler,
} from 'lucide-react'
import type { Lang } from '@/lib/mortra/i18n'
import { LabNotchNav } from './LabNotchNav'
import { ShaderField } from './ShaderField'
import styles from '@/app/research/engineering-geometry/engineeringGeometry.module.css'

const operations = [
  ['transform', '位置・向き・対称性を変える'],
  ['sweep', '断面を経路に沿って運ぶ'],
  ['combine', '形状の和・差・共通部分を取る'],
  ['select', '面・辺・境界を選ぶ'],
  ['slice', '切断面との交わりを取る'],
  ['project', '正投影・等角投影へ写す'],
  ['constrain', '寸法と成立条件を検査する'],
  ['annotate', '寸法・中心線・注記を結び付ける'],
] as const

const drawings = [
  {
    src: '/research/engineering-geometry/declarative-flange-semantics.svg',
    id: 'FLG-SEM-001',
    en: 'Six-hole flange with engineering semantics',
    ja: '工学情報付き6穴フランジ',
    detailEn: 'Third-angle views, section, dimensions, material, tolerances, datum, load and calculated mass from one B-rep.',
    detailJa: '一つの境界表現から、第三角法、断面、寸法、材料、公差、基準、荷重、質量を生成。',
  },
  {
    src: '/research/engineering-geometry/normal-offset-gasket.svg',
    id: 'NGS-001',
    en: 'Normal-offset gasket',
    ja: '法線オフセット・ガスケット',
    detailEn: 'A parallel set, Boolean difference and linear sweep from one normal-bundle rule.',
    detailJa: '平行集合、形状差、直線掃引を一つの法線束規則から構成。',
  },
  {
    src: '/research/engineering-geometry/thin-wall-enclosure.svg',
    id: 'ENC-001',
    en: 'Open thin-wall enclosure',
    ja: '開放薄肉箱',
    detailEn: 'A selected opening face and normal interval generate the wall layer and section.',
    detailJa: '開口面の選択と法線区間から壁層と断面を生成。',
  },
  {
    src: '/research/engineering-geometry/filleted-post.svg',
    id: 'BLD-001',
    en: 'Rolling-ball edge blend',
    ja: '4辺の円弧角丸',
    detailEn: 'Four selected edges share the same disk-sector sweep used by planar corner blends.',
    detailJa: '選択した4辺へ、平面角丸と共通の円板扇形掃引を適用。',
  },
  {
    src: '/research/engineering-geometry/rounded-link-plate.svg',
    id: 'LNK-001',
    en: 'Rounded link plate',
    ja: '丸端2穴リンク板',
    detailEn: 'A finite line-and-arc sketch, two holes and an exact closed-form volume.',
    detailJa: '有限な線分・円弧スケッチと2穴から構成し、体積を閉形式で検査。',
  },
  {
    src: '/research/engineering-geometry/spoked-wheel.svg',
    id: 'SPK-001',
    en: 'Spoked wheel',
    ja: 'スポーク車輪',
    detailEn: 'Repeated transforms, swept profiles and Boolean union.',
    detailJa: '反復変換、断面の移動、形状の和で構成。',
  },
  {
    src: '/research/engineering-geometry/clevis-bracket.svg',
    id: 'CLV-001',
    en: 'Clevis bracket',
    ja: 'クレビス',
    detailEn: 'Paired lugs, cross bore and an exact section from one B-rep.',
    detailJa: '二枚のラグと横穴を持つB-repから断面を導出。',
  },
  {
    src: '/research/engineering-geometry/cross-drilled-manifold.svg',
    id: 'MNF-001',
    en: 'Cross-drilled manifold',
    ja: '三軸交差流路ブロック',
    detailEn: 'Three orthogonal passages, hidden lines and clipped hatching.',
    detailJa: '三方向の流路、隠れ線、断面ハッチを同じ形状から生成。',
  },
] as const

const pipeline = [
  ['01', 'Finite program', '有限JSONと8射で構成を記録'],
  ['02', 'Exact backend', '3次元B-repまたは高次元有理セルを実行'],
  ['03', 'Derived views', '投影、隠れ線、断面をB-repから導出'],
  ['04', 'Engineering semantics', '材料、公差、基準、接合、荷重を形状へ接続'],
  ['05', 'Artifacts', 'STEP、STL、SVG、DXF、JSONを保存'],
] as const

const resultRows = [
  ['有限入力プログラム', 'Finite-input programs', '6 / 6', '曲線部品、平行集合、薄肉化、角丸を任意B-rep入力なしで実行', 'Curve-based parts, parallel sets, thin walls and blends executed without arbitrary B-rep inputs'],
  ['工学情報の因果比較', 'Engineering-semantics causal checks', '3 / 3', '材料、公差、基準、荷重を加えても形状と8操作の使用回数は不変', 'Geometry and all eight operation counts stayed unchanged after adding material, tolerances, datums and loads'],
  ['閉形式体積', 'Closed-form volumes', '6 / 6', '数値の正体積だけでなく、各形状の幾何式と照合', 'Checked against a geometric formula, not only positive numerical volume'],
  ['高次元セル', 'Higher-dimensional cells', '4D–12D', '同じ sweep と project で厳密有理セルを構成・射影', 'Exact rational cells constructed and projected with the same sweep and project operations'],
  ['広域回帰試験', 'Geometry regression suite', '57 / 57', '機械製図、宣言的CAD、生成幾何、異分野間変換、高次元セルを一括検査', 'Mechanical drawing, declarative CAD, generative geometry, cross-domain transforms and higher-dimensional cells all passed'],
  ['外部操作の構造被覆', 'External operation coverage', '23,946 / 24,213', 'CADTestBench 2,400プログラムの構成呼び出しを静的に監査', 'Static audit of construction calls in 2,400 CADTestBench programs'],
  ['完全被覆ファイル', 'Fully covered files', '2,277 / 2,400', '各ファイル内の構成呼び出しがすべて現在の実行系に対応', 'Every construction call in each file maps to the current runtime'],
  ['追加した幾何操作', 'Added geometry operations', '0', '工学情報と12次元実行のための部品別命令は追加していない', 'No part-specific operation was added for engineering semantics or 12-dimensional execution'],
] as const

const dimensionRows = [
  ['3D', '3 / 3', 'semantic cases', 'STEP / STL / SVG / DXF / JSON'],
  ['4D', '16', 'vertices', '32 edges'],
  ['6D', '64', 'vertices', '192 edges'],
  ['8D', '256', 'vertices', '1,024 edges'],
  ['10D', '1,024', 'vertices', '5,120 edges'],
  ['12D', '4,096', 'vertices', '24,576 edges'],
] as const

export function EngineeringGeometryResearchPage({ lang = 'en' }: { lang?: Lang }) {
  const ja = lang === 'ja'
  const research = ja ? '/ja/research' : '/research'
  const counterpart = ja ? '/research/engineering-geometry' : '/ja/research/engineering-geometry'

  return (
    <main className={styles.page} id="top">
      <ShaderField className={styles.backgroundField} />
      <div className={styles.backgroundVeil} aria-hidden="true" />
      <LabNotchNav lang={lang} active="research" alternateHref={counterpart} />

      <section className={styles.hero}>
        <div className={styles.shell}>
          <Link className={styles.backLink} href={research}>
            <ArrowLeft size={14} aria-hidden="true" />
            {ja ? '研究一覧' : 'Research index'}
          </Link>

          <div className={styles.heroCopy}>
            <p className={styles.sectionLabel}>ENGINEERING GEOMETRY / 2026.08.31</p>
            <h1>{ja ? '同じ8つの射から、立体と図面を生成する。' : 'One set of eight morphisms produces both solids and drawings.'}</h1>
            <p>{ja
              ? '有限な線・円弧・経路と8つの共通操作から、厳密な3D形状、第三角法、断面、寸法を生成します。同じ形状へ材料、公差、基準、荷重を接続し、12次元まで同じ型規則を実行しました。'
              : 'Finite lines, arcs and paths combine with eight generic operations to produce exact 3D solids, third-angle drawings, sections and dimensions. The same shape receives material, tolerance, datum and load semantics, while the shared type rules execute through 12 dimensions.'}</p>
          </div>

          <div className={styles.metricRail} aria-label={ja ? '実験結果' : 'Experiment results'}>
            <div><strong>8</strong><span>{ja ? '共通射' : 'generic morphisms'}</span></div>
            <div><strong>3 / 3</strong><span>{ja ? '工学情報の因果比較' : 'semantic causal checks'}</span></div>
            <div><strong>4–12D</strong><span>{ja ? '厳密セル実行' : 'exact cell execution'}</span></div>
            <div><strong>57 / 57</strong><span>{ja ? '広域回帰試験' : 'geometry regression tests'}</span></div>
          </div>

          <figure className={styles.heroDrawing}>
            <Image
              src="/research/engineering-geometry/declarative-flange-semantics.svg"
              alt={ja ? 'MORTRAが生成した工学情報付き6穴フランジの第三角法機械図面' : 'Third-angle mechanical drawing of a six-hole flange with engineering semantics generated by MORTRA'}
              fill
              priority
              unoptimized
              sizes="(max-width: 900px) 100vw, 1240px"
            />
            <figcaption>
              <span>FLG-SEM-001</span>
              {ja ? '第三角法・断面・寸法・材料・公差・基準・荷重・質量' : 'Third-angle projection, section, dimensions, material, tolerances, datum, load and mass'}
            </figcaption>
          </figure>
        </div>
      </section>

      <section className={styles.section} id="basis">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionLabel}>01 / GENERATIVE BASIS</p>
              <h2>{ja ? '部品ではなく、操作を記述する。' : 'Describe operations, not parts.'}</h2>
            </div>
            <p>{ja
              ? '押出し、回転、ロフトは別の原始命令ではありません。いずれも断面を経路に沿って運ぶ sweep の条件違いです。部品名を覚えず、構成の合成だけを保存します。'
              : 'Extrusion, revolution and lofting are not separate primitives. They are parameterizations of sweep: transporting a section along a path. MORTRA stores compositions, not part names.'}</p>
          </div>

          <div className={styles.operationGrid}>
            {operations.map(([name, description], index) => (
              <div key={name}>
                <span>{String(index + 1).padStart(2, '0')}</span>
                <code>{name}</code>
                <p>{ja ? description : [
                  'Change position, orientation or symmetry',
                  'Transport a section along a trajectory',
                  'Take union, difference or intersection',
                  'Select faces, edges or boundaries',
                  'Intersect a shape with a cutting flat',
                  'Map a solid to orthographic or isometric views',
                  'Check dimensions and validity conditions',
                  'Attach dimensions, centrelines and notes',
                ][index]}</p>
              </div>
            ))}
          </div>

          <div className={styles.typeRule}>
            <div>
              <span>{ja ? '同じ型規則' : 'ONE TYPE RULE'}</span>
              <strong>sweep<sub>d</sub> : Cell(k, R<sup>n</sup>) → Cell(min(k+d,n), R<sup>n</sup>)</strong>
            </div>
            <p>{ja
              ? '平面断面を3次元へ押し出す場合も、3次元セルを4次元へ運ぶ場合も語彙は同じです。OpenCascadeは厳密な3次元B-repを、有理セル実行系は4次元以上の有限セルを扱います。'
              : 'The vocabulary is unchanged when a plane section becomes a 3D solid or a 3D cell is swept into 4D. OpenCascade executes exact 3D B-reps; the rational-cell backend executes finite cells in four or more dimensions.'}</p>
          </div>
        </div>
      </section>

      <section className={`${styles.section} ${styles.dimensionSection}`} id="dimensions">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionLabel}>02 / DIMENSION-INDEPENDENT EXECUTION</p>
              <h2>{ja ? '次元が変わっても、射は同じ。' : 'More dimensions, no new morphisms.'}</h2>
            </div>
            <p>{ja
              ? '3次元の機械部品と4次元以上の有限セルは、実行系だけを切り替えます。操作名と型規則は共通で、座標と射の履歴は厳密な有理数として保存します。'
              : 'Three-dimensional machine parts and finite cells above three dimensions use different execution backends. Operation names and type rules stay shared, while coordinates and morphism histories remain exact rational data.'}</p>
          </div>

          <div className={styles.dimensionShowcase}>
            <figure className={styles.dimensionCanvas}>
              <Image
                src="/research/engineering-geometry/hypercube-8d.svg"
                alt={ja ? 'MORTRAが厳密な有理座標で生成した8次元立方体の2次元射影' : 'Two-dimensional projection of an 8D hypercube generated by MORTRA with exact rational coordinates'}
                fill
                loading="eager"
                unoptimized
                sizes="(max-width: 900px) 100vw, 700px"
              />
              <figcaption>{ja ? '8次元立方体 / 256頂点・1,024辺 / 厳密有理射影' : '8D hypercube / 256 vertices, 1,024 edges / exact rational projection'}</figcaption>
            </figure>

            <div className={styles.dimensionData}>
              {dimensionRows.map(([dimension, value, unit, detail]) => (
                <div key={dimension}>
                  <span>{dimension}</span>
                  <strong>{value}</strong>
                  <p>{unit}<small>{detail}</small></p>
                </div>
              ))}
              <p className={styles.dimensionNote}>{ja
                ? '1次元から12次元まで、頂点数 2ⁿ と辺数 n·2ⁿ⁻¹を回帰試験で照合しました。高次元では、有限頂点と有限辺を持つアフィンセルを有理数で厳密に実行します。'
                : 'Regression tests cover dimensions 1 through 12 and verify 2ⁿ vertices and n·2ⁿ⁻¹ edges. In higher dimensions MORTRA executes finite affine cells with exact rational coordinates.'}</p>
            </div>
          </div>
        </div>
      </section>

      <section className={`${styles.section} ${styles.pipelineSection}`} id="pipeline">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionLabel}>03 / ONE CONSTRUCTION DAG</p>
              <h2>{ja ? '立体と図面を、別々に描かない。' : 'The solid and drawing are never authored separately.'}</h2>
            </div>
            <p>{ja
              ? '表示用の輪郭を手書きせず、投影線、隠れ線、断面、ハッチを同じ境界表現から導出します。材料、公差、基準、荷重も同じ対象へ結び付くため、形状を直すと図面と工学情報が同時に更新されます。'
              : 'No display outline is hand-authored. Projection lines, hidden lines, sections and hatching derive from one boundary representation. Material, tolerance, datum and load assertions reference the same entities, so geometry and engineering information update together.'}</p>
          </div>

          <div className={styles.pipeline}>
            {pipeline.map(([index, title, detail], itemIndex) => (
              <div key={title}>
                <span>{index}</span>
                <strong>{title}</strong>
                <p>{ja ? detail : [
                  'Record the construction with finite JSON and eight morphisms',
                  'Execute an exact 3D B-rep or higher-dimensional rational cell',
                  'Derive projection, hidden lines and sections from the B-rep',
                  'Attach material, tolerances, datums, joints and loads to referenced entities',
                  'Persist STEP, STL, SVG, DXF and replay JSON',
                ][itemIndex]}</p>
                {itemIndex < pipeline.length - 1 ? <ArrowRight size={15} aria-hidden="true" /> : null}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.section} id="drawings">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionLabel}>04 / STRUCTURAL HOLDOUTS</p>
              <h2>{ja ? '名前ではなく、構造を変えて試す。' : 'Change the structure, not just the name.'}</h2>
            </div>
            <p>{ja
              ? '平行集合、薄肉境界層、円板扇形の包絡、反復スポーク、二枚ラグ、三軸交差流路を、演算集合を変えずに生成しました。角丸・薄肉化・平面オフセットは別命令ではなく、同じ法線束の掃引です。'
              : 'Parallel sets, thin boundary layers, disk-sector envelopes, repeated spokes, paired lugs and intersecting passages were generated without changing the operator set. Fillets, shells and planar offsets are one normal-bundle sweep, not separate commands.'}</p>
          </div>

          <div className={styles.drawingList}>
            {drawings.map(drawing => (
              <figure key={drawing.id}>
                <div className={styles.drawingCanvas}>
                  <Image src={drawing.src} alt={ja ? `${drawing.ja}の機械図面` : `Mechanical drawing of ${drawing.en}`} fill unoptimized sizes="(max-width: 900px) 100vw, 1200px" />
                </div>
                <figcaption>
                  <span>{drawing.id}</span>
                  <strong>{ja ? drawing.ja : drawing.en}</strong>
                  <p>{ja ? drawing.detailJa : drawing.detailEn}</p>
                </figcaption>
              </figure>
            ))}
          </div>
        </div>
      </section>

      <section className={`${styles.section} ${styles.resultsSection}`} id="results">
        <div className={styles.shell}>
          <div className={styles.sectionHead}>
            <div>
              <p className={styles.sectionLabel}>05 / MEASURED RESULT</p>
              <h2>{ja ? '形状と成果物で示す。' : 'Verify geometry and artifacts, not screenshots alone.'}</h2>
            </div>
            <p>{ja
              ? '既存6部品では境界表現と閉形式体積を検査しました。さらに3部品へ工学情報を追加し、形状と8操作が変わらないことを比較しました。第三角法、断面、寸法、STEP、STL、SVG、DXF、JSONを同じ構成から生成しています。'
              : 'Six existing parts verify boundary-representation validity and closed-form volume. Three additional causal comparisons attach engineering semantics and confirm that geometry and all eight operations remain unchanged. Third-angle drawings, sections, dimensions, STEP, STL, SVG, DXF and JSON derive from the same construction.'}</p>
          </div>

          <div className={styles.resultTable}>
            {resultRows.map(([labelJa, labelEn, value, noteJa, noteEn]) => (
              <div key={labelEn}>
                <span>{ja ? labelJa : labelEn}</span>
                <strong>{value}</strong>
                <p>{ja ? noteJa : noteEn}</p>
              </div>
            ))}
          </div>

          <div className={styles.artifactLinks}>
            <a href="/research/engineering-geometry/declarative-flange-semantics.step" download>
              <Box size={18} aria-hidden="true" /><span><b>STEP</b><small>{ja ? '工学情報付き6穴フランジ' : 'six-hole flange with engineering semantics'}</small></span><Download size={14} aria-hidden="true" />
            </a>
            <a href="/research/engineering-geometry/declarative-flange-semantics.dxf" download>
              <Ruler size={18} aria-hidden="true" /><span><b>DXF</b><small>{ja ? '材料・公差・荷重付き第三角法図面' : 'third-angle drawing with material, tolerance and load data'}</small></span><Download size={14} aria-hidden="true" />
            </a>
            <a href="/research/engineering-geometry/hypercube-8d.svg" target="_blank" rel="noreferrer">
              <Layers3 size={18} aria-hidden="true" /><span><b>{ja ? '8次元射影' : '8D projection'}</b><small>{ja ? '厳密有理座標によるSVG' : 'SVG from exact rational coordinates'}</small></span><ArrowRight size={14} aria-hidden="true" />
            </a>
            <a href="/research/engineering-geometry/engineering-semantics-summary.json" target="_blank" rel="noreferrer">
              <FileJson2 size={18} aria-hidden="true" /><span><b>{ja ? '意味層・12次元実験' : 'Semantics and 12D results'}</b><small>{ja ? '3部品と5次元条件の全記録' : 'all records for three parts and five dimension cases'}</small></span><ArrowRight size={14} aria-hidden="true" />
            </a>
            <a href="/research/engineering-geometry/cadtestbench-operator-coverage.json" target="_blank" rel="noreferrer">
              <FileJson2 size={18} aria-hidden="true" /><span><b>{ja ? '構造監査' : 'Structural audit'}</b><small>{ja ? '2,400プログラム' : '2,400 programs'}</small></span><ArrowRight size={14} aria-hidden="true" />
            </a>
            <a href="https://github.com/corcondor/mortra/blob/release/mortra-1-beta/docs/research/MORTRA-ENGINEERING-SEMANTICS-AND-ND-GENERALIZATION-20260831.md" target="_blank" rel="noreferrer">
              <Github size={18} aria-hidden="true" /><span><b>{ja ? '研究記録' : 'Research record'}</b><small>{ja ? '原理・方法・結果・限界' : 'principle, method, result and limits'}</small></span><ArrowRight size={14} aria-hidden="true" />
            </a>
          </div>
        </div>
      </section>

      <section className={styles.section} id="boundary">
        <div className={`${styles.shell} ${styles.boundaryGrid}`}>
          <div>
            <p className={styles.sectionLabel}>06 / NEXT ENGINEERING LAYER</p>
            <h2>{ja ? '次に接続するのは、解析と製造判断。' : 'Next: analysis and manufacturing decisions.'}</h2>
          </div>
          <div className={styles.boundaryCopy}>
            <p>{ja
              ? '材料、密度、加工法、公差、表面粗さ、基準、接合、力、モーメントは、property・relation・actionの三形式で接続しました。次は同じ対象参照を保ったまま、幾何公差、溶接記号、部品表、応力、疲労、熱へ拡張します。'
              : 'Material, density, process, tolerance, surface finish, datums, joints, forces and moments now share three forms: property, relation and action. The next step preserves the same entity references while extending to geometric tolerancing, weld symbols, bills of materials, stress, fatigue and heat.'}</p>
            <p>{ja
              ? '物理的な製品形状と機械図面は3次元の境界表現で扱います。4次元以上は、機構の配位空間、状態空間、設計変数空間へ使える厳密なアフィンセルとして扱います。この役割分担により、機械製図の正確さと高次元数学の一般性を同じ8操作で共有できます。'
              : 'Physical product geometry and mechanical drawings use three-dimensional boundary representations. Higher dimensions use exact affine cells for configuration spaces, state spaces and design-variable spaces. This separation shares the same eight operations without confusing physical drawings with higher-dimensional mathematics.'}</p>
          </div>
        </div>
      </section>

      <footer className={styles.footer}>
        <div className={styles.shell}>
          <span><Layers3 size={14} aria-hidden="true" />MORTRA / ENGINEERING GEOMETRY</span>
          <Link href={research}>{ja ? '研究一覧へ戻る' : 'Back to research'}<ArrowRight size={13} /></Link>
        </div>
      </footer>
    </main>
  )
}
