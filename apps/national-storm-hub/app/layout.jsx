import "./globals.css";
import ThemeReview from "../components/ThemeReview.jsx";
export const metadata = {
  metadataBase: new URL("https://nationalstormhub.com"),
  title: "National Storm Hub | Weather intelligence & home preparedness",
  description: "Explore official US weather alerts, save an area in your Storm Passport, and learn how to prepare and recover responsibly.",
  robots: {index:false, follow:false},
  alternates: {canonical:"/"},
  openGraph: {title:"National Storm Hub",type:"website",siteName:"National Storm Hub"},
};
export default function RootLayout({children}) {
  return <html lang="en"><body>{children}<ThemeReview/></body></html>;
}
