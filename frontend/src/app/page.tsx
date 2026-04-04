'use client';

import Link from 'next/link';
import { CheckCircle, Camera, FileText, Pen } from 'lucide-react';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-brand-50 to-white">
      {/* Nav */}
      <nav className="flex items-center justify-between max-w-6xl mx-auto px-6 py-5">
        <div className="flex items-center gap-2">
          <Pen className="w-7 h-7 text-brand-600" />
          <span className="text-xl font-bold text-brand-900">ClassPal</span>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/auth" className="text-sm text-brand-700 hover:text-brand-900">
            Log in
          </Link>
          <Link
            href="/auth?mode=register"
            className="text-sm bg-brand-600 text-white px-4 py-2 rounded-lg hover:bg-brand-700 transition-colors"
          >
            Get Started Free
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-4xl mx-auto px-6 pt-20 pb-16 text-center">
        <h1 className="text-5xl font-bold text-brand-950 leading-tight tracking-tight">
          Grade papers in minutes,
          <br />
          <span className="text-brand-600">not hours</span>
        </h1>
        <p className="mt-6 text-lg text-gray-600 max-w-2xl mx-auto">
          Scan student papers with your phone, let AI read and grade handwritten
          answers, then review corrections that look like they were marked by hand.
        </p>
        <div className="mt-10 flex items-center justify-center gap-4">
          <Link
            href="/auth?mode=register"
            className="bg-brand-600 text-white px-8 py-3 rounded-xl text-base font-medium hover:bg-brand-700 transition-colors shadow-lg shadow-brand-600/25"
          >
            Start Free Trial
          </Link>
          <Link
            href="#how-it-works"
            className="text-brand-700 px-6 py-3 rounded-xl text-base font-medium hover:bg-brand-100 transition-colors"
          >
            See How It Works
          </Link>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="max-w-5xl mx-auto px-6 py-20">
        <h2 className="text-3xl font-bold text-center text-brand-950 mb-14">
          How It Works
        </h2>
        <div className="grid md:grid-cols-3 gap-10">
          {[
            {
              icon: Camera,
              title: 'Scan',
              desc: 'Photograph student papers with your phone camera or upload from your computer.',
            },
            {
              icon: CheckCircle,
              title: 'AI Grades',
              desc: 'AI reads handwritten answers, evaluates correctness, and suggests marks with natural pen-style annotations.',
            },
            {
              icon: FileText,
              title: 'Review & Export',
              desc: 'Review AI suggestions, adjust any marks, then download or print the corrected paper.',
            },
          ].map((step, i) => (
            <div key={i} className="text-center">
              <div className="w-14 h-14 rounded-2xl bg-brand-100 text-brand-600 flex items-center justify-center mx-auto mb-4">
                <step.icon className="w-7 h-7" />
              </div>
              <h3 className="text-lg font-semibold text-brand-950 mb-2">{step.title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-8 text-center text-sm text-gray-500">
        &copy; {new Date().getFullYear()} ClassPal. Built by Venushub CY LTD.
      </footer>
    </div>
  );
}
