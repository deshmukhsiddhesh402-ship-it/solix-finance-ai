import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth-options";

export async function getBackendAuthHeaders() {
  const session = await getServerSession(authOptions);
  const user = session?.user as
    | { id?: string; accessToken?: string; orgId?: string }
    | undefined;

  if (!user?.id || !user.accessToken || !user.orgId) return null;

  return {
    userId: user.id,
    orgId: user.orgId,
    headers: {
      Authorization: `Bearer ${user.accessToken}`,
    },
  };
}
