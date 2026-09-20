import type { Metadata, Viewport } from 'next'
import { Inter, Space_Grotesk } from 'next/font/google'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-space-grotesk',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Odd Worlds — Exoplanetas anomalos',
  description:
    'Habla con un agente especialista en exoplanetas anomalos. Explora mundos confirmados del NASA Exoplanet Archive.',
}

export const viewport: Viewport = {
  colorScheme: 'dark',
  themeColor: '#12131f',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="es" className={`dark ${inter.variable} ${spaceGrotesk.variable}`}>
      <body className="bg-background font-sans antialiased">
        {children}
      </body>
    </html>
  )
}
