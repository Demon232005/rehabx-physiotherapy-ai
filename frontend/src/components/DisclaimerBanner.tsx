export default function DisclaimerBanner({ text }: { text?: string }) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
      <strong className="font-semibold">Disclaimer: </strong>
      {text ??
        "This is an AI-assisted research/prototype system. It does not provide a medical diagnosis and does not replace evaluation by a qualified physician or physiotherapist."}
    </div>
  );
}
