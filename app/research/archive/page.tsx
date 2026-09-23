import { ArchivedProductPage } from '@/components/mortra/ArchivedProductPage'
export const metadata = { title: 'MORTRA | Archived earlier work', robots: { index: false } }
export default function Archive() {
  return <><div role="note" style={{ padding: '30px 24px', background: '#f3ead3', color: '#403617', position: 'relative', zIndex: 50 }}>ARCHIVED / AUDIT / EXPERIMENTAL · Earlier mathematics and proof presentation. Historical figures are not current verified benchmarks.</div><ArchivedProductPage lang="en" /></>
}
