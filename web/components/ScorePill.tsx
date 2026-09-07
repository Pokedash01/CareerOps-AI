export default function ScorePill({ score }: { score: number }) {
  const cls = score >= 70 ? "chip-emerald" : score >= 40 ? "chip-amber" : "chip-rose";
  return <span className={cls}>{score}%</span>;
}
