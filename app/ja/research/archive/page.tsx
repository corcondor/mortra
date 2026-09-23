import { ArchivedProductPage } from '@/components/mortra/ArchivedProductPage'
export const metadata = { title: 'MORTRA | Archived earlier work', robots: { index: false } }
export default function Archive() {
  return <><div role="note" style={{ padding: '30px 24px', background: '#f3ead3', color: '#403617', position: 'relative', zIndex: 50 }}>ARCHIVED / AUDIT / EXPERIMENTAL · 以前の数学・証明紹介を保存したページです。旧数値は現在の検証結果ではありません。</div><ArchivedProductPage lang="ja" /></>
}
