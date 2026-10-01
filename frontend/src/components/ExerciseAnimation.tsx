"use client";

const styleMap: Record<string, string> = {
  "finger-flexion": `
    @keyframes curl-fingers {
      0%, 100% { d: path("M40,45 Q42,30 40,20"); }
      50% { d: path("M40,45 Q35,35 38,30"); }
    }
    .fc1 { animation: curl-fingers 2s ease-in-out infinite; }
    .fc2 { animation: curl-fingers 2s ease-in-out infinite 0.15s; }
    .fc3 { animation: curl-fingers 2s ease-in-out infinite 0.3s; }
    .fc4 { animation: curl-fingers 2s ease-in-out infinite 0.45s; }
    .fc5 { animation: curl-fingers 2s ease-in-out infinite 0.6s; }
  `,
  "finger-extension": `
    @keyframes extend-fingers {
      0%, 100% { d: path("M40,45 Q35,35 38,30"); }
      50% { d: path("M40,45 Q42,28 40,15"); }
    }
    .fe1 { animation: extend-fingers 2s ease-in-out infinite; }
    .fe2 { animation: extend-fingers 2s ease-in-out infinite 0.15s; }
    .fe3 { animation: extend-fingers 2s ease-in-out infinite 0.3s; }
    .fe4 { animation: extend-fingers 2s ease-in-out infinite 0.45s; }
    .fe5 { animation: extend-fingers 2s ease-in-out infinite 0.6s; }
  `,
  "finger-spreading": `
    @keyframes spread-left { 0%, 100% { transform: translateX(0); } 50% { transform: translateX(-5px); } }
    @keyframes spread-right { 0%, 100% { transform: translateX(0); } 50% { transform: translateX(5px); } }
    .fs1 { animation: spread-left 2.5s ease-in-out infinite; }
    .fs2 { animation: spread-left 2.5s ease-in-out infinite 0.1s; }
    .fs3 { animation: spread-right 2.5s ease-in-out infinite 0.2s; }
    .fs4 { animation: spread-right 2.5s ease-in-out infinite 0.3s; }
  `,
  "wrist-flexion": `
    @keyframes wrist-flex {
      0%, 100% { transform: rotate(0deg); }
      50% { transform: rotate(25deg); }
    }
    .wf { transform-origin: 60px 50px; animation: wrist-flex 2s ease-in-out infinite; }
  `,
  "wrist-extension": `
    @keyframes wrist-ext {
      0%, 100% { transform: rotate(0deg); }
      50% { transform: rotate(-25deg); }
    }
    .we { transform-origin: 60px 50px; animation: wrist-ext 2s ease-in-out infinite; }
  `,
  "wrist-circumduction": `
    @keyframes wrist-circle {
      0% { transform: rotate(0deg) translateY(0); }
      25% { transform: rotate(10deg) translateY(-3px); }
      50% { transform: rotate(0deg) translateY(-6px); }
      75% { transform: rotate(-10deg) translateY(-3px); }
      100% { transform: rotate(0deg) translateY(0); }
    }
    .wc { transform-origin: 60px 55px; animation: wrist-circle 3s ease-in-out infinite; }
  `,
  "grip-strength": `
    @keyframes grip {
      0%, 100% { transform: scale(1); }
      50% { transform: scale(0.88); }
    }
    .gs { transform-origin: 55px 40px; animation: grip 1.8s ease-in-out infinite; }
    @keyframes squeeze-ball {
      0%, 100% { r: 8; }
      50% { r: 6; }
    }
    .gb { animation: squeeze-ball 1.8s ease-in-out infinite; }
  `,
  "thumb-opposition": `
    @keyframes thumb-move {
      0%, 100% { transform: translateX(0) translateY(0); }
      50% { transform: translateX(10px) translateY(5px); }
    }
    .to { transform-origin: 30px 55px; animation: thumb-move 2.2s ease-in-out infinite; }
  `,
  "forearm-pronation": `
    @keyframes pronate {
      0%, 100% { transform: scaleX(1); }
      50% { transform: scaleX(0.4); }
    }
    .fp { transform-origin: 60px 55px; animation: pronate 2.5s ease-in-out infinite; }
  `,
  "forearm-supination": `
    @keyframes supinate {
      0%, 100% { transform: scaleX(0.4); }
      50% { transform: scaleX(1); }
    }
    .fsp { transform-origin: 60px 55px; animation: supinate 2.5s ease-in-out infinite; }
  `,
  "elbow-bend": `
    @keyframes elbow-bend {
      0%, 100% { transform: rotate(0deg); }
      50% { transform: rotate(75deg); }
    }
    .eb { transform-origin: 60px 78px; animation: elbow-bend 2.4s ease-in-out infinite; }
  `,
  "shoulder-raise": `
    @keyframes shoulder-raise {
      0%, 100% { transform: rotate(0deg); }
      50% { transform: rotate(-80deg); }
    }
    .sr { transform-origin: 52px 82px; animation: shoulder-raise 2.8s ease-in-out infinite; }
  `,
};

function getAnimationId(slug: string) {
  const direct = Object.keys(styleMap).find((k) => slug.includes(k));
  if (direct) return direct;
  // keyword fallbacks so arm exercises get a sensible animation
  if (slug.includes("elbow")) return "elbow-bend";
  if (
    slug.includes("shoulder") ||
    slug.includes("scapular") ||
    slug.includes("raise") ||
    slug.includes("slides")
  ) {
    return "shoulder-raise";
  }
  return null;
}

function FingerFlexion() {
  return (
    <g>
      <line x1="55" y1="75" x2="55" y2="45" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
      <path d="M40,45 Q42,30 40,20" fill="none" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" className="fc1" />
      <path d="M47,43 Q48,26 47,17" fill="none" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" className="fc2" />
      <path d="M55,42 Q55,24 55,15" fill="none" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" className="fc3" />
      <path d="M63,43 Q63,26 63,17" fill="none" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" className="fc4" />
      <path d="M70,45 Q68,32 70,23" fill="none" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" className="fc5" />
      <path d="M35,55 Q30,50 32,45" fill="none" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
    </g>
  );
}

function FingerExtension() {
  return (
    <g>
      <line x1="55" y1="75" x2="55" y2="45" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
      <path d="M40,45 Q35,35 38,30" fill="none" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" className="fe1" />
      <path d="M47,43 Q45,30 47,20" fill="none" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" className="fe2" />
      <path d="M55,42 Q55,28 55,15" fill="none" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" className="fe3" />
      <path d="M63,43 Q63,28 63,17" fill="none" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" className="fe4" />
      <path d="M70,45 Q72,30 70,20" fill="none" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" className="fe5" />
      <path d="M35,55 Q28,50 30,44" fill="none" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
    </g>
  );
}

function FingerSpreading() {
  return (
    <g>
      <line x1="55" y1="75" x2="55" y2="48" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
      <line x1="47" y1="48" x2="42" y2="22" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" className="fs1" />
      <line x1="51" y1="46" x2="49" y2="18" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" className="fs2" />
      <line x1="55" y1="45" x2="55" y2="16" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
      <line x1="59" y1="46" x2="61" y2="18" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" className="fs3" />
      <line x1="63" y1="48" x2="68" y2="22" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" className="fs4" />
      <path d="M38,58 Q32,52 34,46" fill="none" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
    </g>
  );
}

function WristFlexion() {
  return (
    <g>
      <rect x="50" y="55" width="12" height="30" rx="3" fill="none" stroke="#0d9488" strokeWidth="2" />
      <g className="wf">
        <line x1="50" y1="55" x2="42" y2="28" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
        <line x1="62" y1="55" x2="54" y2="28" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
        <line x1="42" y1="28" x2="36" y2="22" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
        <line x1="46" y1="27" x2="42" y2="19" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
        <line x1="50" y1="26" x2="48" y2="17" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
        <line x1="54" y1="27" x2="54" y2="18" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
      </g>
    </g>
  );
}

function WristExtension() {
  return (
    <g>
      <rect x="50" y="55" width="12" height="30" rx="3" fill="none" stroke="#0d9488" strokeWidth="2" />
      <g className="we">
        <line x1="50" y1="55" x2="42" y2="28" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
        <line x1="62" y1="55" x2="54" y2="28" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
        <line x1="42" y1="28" x2="36" y2="22" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
        <line x1="46" y1="27" x2="42" y2="19" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
        <line x1="50" y1="26" x2="48" y2="17" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
        <line x1="54" y1="27" x2="54" y2="18" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
      </g>
    </g>
  );
}

function WristCircumduction() {
  return (
    <g>
      <rect x="50" y="60" width="12" height="25" rx="3" fill="none" stroke="#0d9488" strokeWidth="2" />
      <g className="wc">
        <line x1="50" y1="60" x2="42" y2="35" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
        <line x1="62" y1="60" x2="54" y2="35" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
        <line x1="42" y1="35" x2="37" y2="28" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
        <line x1="46" y1="33" x2="43" y2="25" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
        <line x1="50" y1="32" x2="49" y2="23" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
        <line x1="54" y1="33" x2="55" y2="25" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
        <circle cx="48" cy="18" r="1.5" fill="#0d9488" opacity="0.3" />
        <circle cx="44" cy="15" r="1" fill="#0d9488" opacity="0.2" />
        <circle cx="52" cy="16" r="1" fill="#0d9488" opacity="0.2" />
      </g>
    </g>
  );
}

function GripStrength() {
  return (
    <g>
      <g className="gs">
        <line x1="45" y1="50" x2="38" y2="30" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
        <line x1="50" y1="48" x2="46" y2="26" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
        <line x1="55" y1="47" x2="53" y2="24" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
        <line x1="60" y1="48" x2="60" y2="26" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
        <line x1="65" y1="50" x2="66" y2="30" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M38,55 Q33,48 35,42" fill="none" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
      </g>
      <circle cx="55" cy="38" r="8" fill="#ccfbf1" stroke="#0d9488" strokeWidth="1.5" className="gb" />
    </g>
  );
}

function ThumbOpposition() {
  return (
    <g>
      <line x1="55" y1="75" x2="55" y2="45" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
      <line x1="47" y1="45" x2="44" y2="20" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
      <line x1="53" y1="43" x2="52" y2="18" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
      <line x1="59" y1="43" x2="60" y2="18" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
      <line x1="65" y1="45" x2="67" y2="22" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
      <line x1="37" y1="55" x2="30" y2="50" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" className="to" />
      <circle cx="30" cy="50" r="2" fill="#0d9488" className="to" />
    </g>
  );
}

function ForearmPronation() {
  return (
    <g className="fp">
      <rect x="48" y="35" width="14" height="45" rx="4" fill="none" stroke="#0d9488" strokeWidth="2" />
      <line x1="50" y1="35" x2="44" y2="22" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
      <line x1="55" y1="34" x2="52" y2="20" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
      <line x1="60" y1="35" x2="60" y2="22" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
      <path d="M42,70 Q38,65 39,58" fill="none" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
      <ellipse cx="55" cy="50" rx="5" ry="12" fill="none" stroke="#0d9488" strokeWidth="1" strokeDasharray="3 2" opacity="0.4" />
    </g>
  );
}

function ForearmSupination() {
  return (
    <g className="fsp">
      <rect x="48" y="35" width="14" height="45" rx="4" fill="none" stroke="#0d9488" strokeWidth="2" />
      <line x1="50" y1="35" x2="44" y2="22" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
      <line x1="55" y1="34" x2="52" y2="20" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
      <line x1="60" y1="35" x2="60" y2="22" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
      <path d="M68,70 Q72,65 71,58" fill="none" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
      <ellipse cx="55" cy="50" rx="5" ry="12" fill="none" stroke="#0d9488" strokeWidth="1" strokeDasharray="3 2" opacity="0.4" />
    </g>
  );
}

function GenericHand() {
  return (
    <g>
      <line x1="55" y1="75" x2="55" y2="45" stroke="#0d9488" strokeWidth="2" strokeLinecap="round" />
      <line x1="47" y1="45" x2="43" y2="22" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
      <line x1="51" y1="43" x2="49" y2="18" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
      <line x1="55" y1="42" x2="55" y2="16" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
      <line x1="59" y1="43" x2="61" y2="18" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
      <line x1="63" y1="45" x2="67" y2="22" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M40,55 Q35,48 37,42" fill="none" stroke="#0d9488" strokeWidth="2.5" strokeLinecap="round" />
    </g>
  );
}

function ElbowBend() {
  return (
    <g>
      {/* torso hint */}
      <line x1="52" y1="82" x2="52" y2="100" stroke="#99f6e4" strokeWidth="3" strokeLinecap="round" />
      {/* upper arm (fixed) */}
      <line x1="60" y1="78" x2="78" y2="62" stroke="#0d9488" strokeWidth="4" strokeLinecap="round" />
      {/* forearm bends at the elbow */}
      <g className="eb">
        <line x1="60" y1="78" x2="58" y2="46" stroke="#0d9488" strokeWidth="4" strokeLinecap="round" />
        {/* simple hand */}
        <circle cx="58" cy="44" r="3.5" fill="#ccfbf1" stroke="#0d9488" strokeWidth="1.5" />
      </g>
      <circle cx="60" cy="78" r="2.5" fill="#0d9488" opacity="0.35" />
    </g>
  );
}

function ShoulderRaise() {
  return (
    <g>
      {/* torso hint */}
      <line x1="50" y1="82" x2="50" y2="104" stroke="#99f6e4" strokeWidth="3" strokeLinecap="round" />
      <circle cx="50" cy="76" r="6" fill="none" stroke="#99f6e4" strokeWidth="2.5" />
      {/* whole arm raises from the shoulder */}
      <g className="sr">
        <line x1="54" y1="80" x2="86" y2="88" stroke="#0d9488" strokeWidth="4" strokeLinecap="round" />
        <line x1="86" y1="88" x2="98" y2="90" stroke="#0d9488" strokeWidth="3.5" strokeLinecap="round" />
        <circle cx="101" cy="90" r="3" fill="#ccfbf1" stroke="#0d9488" strokeWidth="1.5" />
      </g>
      <circle cx="54" cy="80" r="2.5" fill="#0d9488" opacity="0.35" />
    </g>
  );
}

const componentMap: Record<string, React.FC> = {
  "finger-flexion": FingerFlexion,
  "finger-extension": FingerExtension,
  "finger-spreading": FingerSpreading,
  "wrist-flexion": WristFlexion,
  "wrist-extension": WristExtension,
  "wrist-circumduction": WristCircumduction,
  "grip-strength": GripStrength,
  "thumb-opposition": ThumbOpposition,
  "forearm-pronation": ForearmPronation,
  "forearm-supination": ForearmSupination,
  "elbow-bend": ElbowBend,
  "shoulder-raise": ShoulderRaise,
};

interface Props {
  slug: string;
  label?: string;
}

export default function ExerciseAnimation({ slug, label }: Props) {
  const animKey = getAnimationId(slug);
  const CSS = animKey ? styleMap[animKey] : "";
  const Content = animKey ? componentMap[animKey] : GenericHand;
  const displayLabel = label ?? "Follow instructions";

  return (
    <div className="flex flex-col items-center">
      {CSS && <style>{CSS}</style>}
      <svg viewBox="0 0 120 120" width="120" height="120" className="block">
        <circle cx="60" cy="60" r="56" fill="#f0fdfa" stroke="#99f6e4" strokeWidth="1.5" />
        <Content />
      </svg>
      <span className="mt-1 text-[10px] font-medium text-teal-700">{displayLabel}</span>
    </div>
  );
}
