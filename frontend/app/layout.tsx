import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'SIH26189 - AI-Powered Criminal Network Analysis System',
  description:
    'Forensic Criminal Network Analysis and Explainable AI (XAI) Evidence Trail System',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 antialiased selection:bg-indigo-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}
