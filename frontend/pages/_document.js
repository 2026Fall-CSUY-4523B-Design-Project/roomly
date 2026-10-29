import Document, { Head, Html, Main, NextScript } from "next/document";

export default class RoomlyDocument extends Document {
  render() {
    return (
      <Html lang="en">
        <Head>
          <meta name="theme-color" content="#f7f4ee" media="(prefers-color-scheme: light)" />
          <meta name="theme-color" content="#151311" media="(prefers-color-scheme: dark)" />
          <meta name="description" content="Search, compare and decide on NYC apartments together with your roommates." />
          <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
          <link rel="preconnect" href="https://fonts.googleapis.com" />
          <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
          <link
            rel="stylesheet"
            href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap"
          />
        </Head>
        <body>
          <Main />
          <NextScript />
        </body>
      </Html>
    );
  }
}
