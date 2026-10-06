/**
 * Shared NextAuth configuration. Kept outside the route module so Next.js
 * route handlers only export HTTP methods.
 */
import { AuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import AzureADProvider from "next-auth/providers/azure-ad";
import CredentialsProvider from "next-auth/providers/credentials";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export const authOptions: AuthOptions = {
  providers: [
    GoogleProvider({ clientId: process.env.GOOGLE_CLIENT_ID || "", clientSecret: process.env.GOOGLE_CLIENT_SECRET || "" }),
    AzureADProvider({
      clientId: process.env.MICROSOFT_CLIENT_ID || "",
      clientSecret: process.env.MICROSOFT_CLIENT_SECRET || "",
      tenantId: process.env.MICROSOFT_TENANT_ID || "common",
    }),
    CredentialsProvider({
      id: "otp",
      name: "Email OTP",
      credentials: {
        email: { label: "Email", type: "email" },
        otp: { label: "OTP", type: "text" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.otp) return null;
        const res = await fetch(`${BACKEND_URL}/api/auth/otp/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: credentials.email, otp: credentials.otp }),
        });
        if (!res.ok) return null;
        const data = await res.json();
        return {
          id: data.user_id,
          email: credentials.email,
          name: data.full_name,
          accessToken: data.access_token,
          orgId: data.org_id,
        };
      },
    }),
  ],
  session: { strategy: "jwt" },
  pages: { signIn: "/login" },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = (user as any).id;
        token.accessToken = (user as any).accessToken;
        token.orgId = (user as any).orgId;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        (session.user as any).id = token.id;
        (session.user as any).accessToken = token.accessToken;
        (session.user as any).orgId = token.orgId;
      }
      return session;
    },
  },
};
