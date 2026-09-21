import "./globals.css";
import ThemeToggle from "../components/ThemeToggle";

export const metadata = {
  title: "Aifa Foods Agro-Processing ERP",
  description:
    "Odoo Community ERP for Yarashoo Agro Industry: farm-gate sourcing, " +
    "dehydration yield control, HACCP gates and farm-to-shelf traceability.",
};

export const viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Applied before paint so a chosen theme never flashes the other one. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('aifa-theme');
if(t){document.documentElement.setAttribute('data-theme',t);}}catch(e){}})();`,
          }}
        />
      </head>
      <body>
        <header className="site-header">
          <div className="inner">
            <div className="logo">
              Aifa<span>.</span>ERP
            </div>
            <nav>
              <a className="hide-sm" href="#finding">Finding</a>
              <a className="hide-sm" href="#workflow">Workflow</a>
              <a className="hide-sm" href="#built">Built</a>
              <a href="#trace">Trace a pack</a>
              <ThemeToggle />
            </nav>
          </div>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
