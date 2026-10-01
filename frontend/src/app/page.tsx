import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-teal-50 via-slate-50 to-slate-100">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-600 text-lg font-bold text-white">
            R
          </span>
          <span className="text-lg font-bold text-slate-900">RehabX AI</span>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="rounded-lg px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200/60"
          >
            Sign in
          </Link>
          <Link
            href="/register"
            className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700"
          >
            Get started
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-24 pt-16">
        <div className="max-w-3xl">
          <h1 className="text-4xl font-extrabold tracking-tight text-slate-900 sm:text-5xl">
            AI-assisted hand &amp; wrist X-ray analysis
          </h1>
          <p className="mt-4 text-lg text-slate-600">
            Upload a radiograph, get a structured AI analysis with detected regions and a
            clinician-reviewed rehabilitation plan — exercises, intensity, and safety guidance
            tailored to the findings.
          </p>
        </div>

        <div className="mt-12 grid gap-6 sm:grid-cols-3">
          {[
            {
              title: "Analyze",
              body: "Real computer-vision pipeline: transfer-learned classifier, Grad-CAM attention, and region localization on your actual X-ray.",
            },
            {
              title: "Recommend",
              body: "A deterministic, knowledge-base-driven engine maps findings to evidence-based exercise categories with rep/set guidance.",
            },
            {
              title: "Track",
              body: "Log exercise sessions and self-reported progress over time to follow your recovery journey.",
            },
          ].map((c) => (
            <div key={c.title} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-lg font-bold text-slate-900">{c.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{c.body}</p>
            </div>
          ))}
        </div>

        <div className="mt-10 max-w-3xl rounded-xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-800">
          <strong>Research prototype.</strong> This system does not provide a medical diagnosis and
          does not replace evaluation by a qualified physician or physiotherapist.
        </div>
      </main>
    </div>
  );
}
