/** `auth.*`: sign-in through the system browser (see ../signin.ts). */

import type { DesktopModule } from "../ipc";
import type { Shell } from "../main";
import { desktopSignIn, desktopSignOut } from "../signin";

export const authModule = (s: Shell): DesktopModule => ({
  namespace: "auth",
  register(ctx) {
    ctx.handle("auth.signIn", async () => {
      const me = await desktopSignIn(ctx.server(), () => s.focus());
      ctx.emit("auth.changed", { signedIn: true });
      return me;
    });
    ctx.handle("auth.signOut", async () => {
      await desktopSignOut(ctx.server());
      ctx.emit("auth.changed", { signedIn: false });
    });
  },
});
