import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "文化遗产跨类型数据组织与研究需求调查",
  description: "CLKG 文化遗产跨类型数据组织与研究需求调查。",
  robots: { index: false, follow: false },
  metadataBase: new URL("https://clkg-heritage-research-survey.mr-sarah435.chatgpt.site"),
  openGraph: {
    title: "文化遗产跨类型数据组织与研究需求调查",
    description: "面向多类型文化遗产研究者的匿名研究需求调研。",
    images: [{ url: "/clkg-heritage-cover.png", width: 1731, height: 909, alt: "跨类型文化遗产数据组织" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "文化遗产跨类型数据组织与研究需求调查",
    description: "面向多类型文化遗产研究者的匿名研究需求调研。",
    images: ["/clkg-heritage-cover.png"],
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
