/**
 * NextAuth configuration — Google + Microsoft OAuth, plus an OTP
 * "credentials" provider that verifies against the FastAPI backend's
 * /api/auth/otp endpoints (see backend/app/routers/auth.py).
 */
import NextAuth from "next-auth";
import { authOptions } from "@/lib/auth-options";

const handler = NextAuth(authOptions);
export { handler as GET, handler as POST };
