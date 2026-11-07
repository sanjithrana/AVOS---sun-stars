import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { ThemeProvider, THEME_BOOTSTRAP_SCRIPT } from "./theme-provider";

export const metadata: Metadata = {
  title: "AVOS - AI Video Operating System",
  description: "Vertically integrated AI Video Operating System",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // Dark by default; the inline script below applies the saved choice
    // before first paint so switching pages/reloading never flashes. suppressHydrationWarning: the class this
    // script sets is expected to differ from the server-rendered markup.
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP_SCRIPT }} />
      </head>
      <body className="antialiased bg-background text-foreground">
        <ThemeProvider>
          <Providers>{children}</Providers>
        </ThemeProvider>
      </body>
    </html>
  );
}