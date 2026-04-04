import type { Metadata } from 'next';
import { DM_Sans, Caveat } from 'next/font/google';
import './globals.css';

const sans = DM_Sans({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
});

const handwriting = Caveat({
  subsets: ['latin'],
  variable: '--font-handwriting',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'ClassPal — AI Paper Grading for Teachers',
  description:
    'Scan student papers, let AI grade handwritten answers, review corrections, and export naturally-marked PDFs.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${handwriting.variable}`}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
