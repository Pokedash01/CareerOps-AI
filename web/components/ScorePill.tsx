export default function ScorePill({ score }: { score: number }) {
  const cls = score >= 70 ? "score-good" : score >= 40 ? "score-mid" : "score-bad";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${cls}`}>
      {score}%
    </span>
  );
}
