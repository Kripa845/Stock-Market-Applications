import fs from "fs";

const file = process.argv[2];
let s = fs.readFileSync(file, "utf8");

const map = [
  ["bg-[#060b16]", "bg-bg-primary"],
  ["bg-[#0a1220]", "bg-bg-card"],
  ["bg-[#0c1626]", "bg-bg-elevated"],
  ["hover:bg-[#101d30]", "hover:bg-blue-500/10"],
  ["border-[#16233a]", "border-bg-border"],
  ["border-[#1e2d47]", "border-bg-border"],
  ["divide-[#16233a]", "divide-bg-border"],
  ["text-white", "text-text-primary"],
  ["text-slate-100", "text-text-primary"],
  ["text-slate-200", "text-text-primary"],
  ["text-slate-300", "text-text-secondary"],
  ["text-slate-400", "text-text-secondary"],
  ["text-slate-500", "text-text-muted"],
  ["text-slate-600", "text-text-muted"],
];

for (const [from, to] of map) s = s.split(from).join(to);
fs.writeFileSync(file, s);
console.log("done:", file);