/* Password gate for the whole site.

   This runs on Netlify's edge, before any file is served, so an unauthenticated
   visitor never receives the deck, the images, or the markup. A client-side
   check would ship the content first and hide it with JavaScript, which is not
   protection. The password lives in the DECK_PASSWORD environment variable, not
   in this file.

   On success we set a cookie holding a SHA-256 of the password plus a fixed
   salt, so the password itself is never stored in the browser. */

const SALT = "everguard-gate-v1";
const COOKIE = "eg_access";
const MAX_AGE = 60 * 60 * 24 * 30; // 30 days, so nobody retypes it every visit

async function token(secret: string): Promise<string> {
  const bytes = new TextEncoder().encode(SALT + ":" + secret);
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(hash)].map(b => b.toString(16).padStart(2, "0")).join("");
}

function page(error: boolean): Response {
  return new Response(
    `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive">
<title>EverGuard</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
 /* Same language as the website and the landing page: flat #090a0b, Barlow
    Condensed set large, DM Sans for the small type, one orange. This screen is
    the first thing she sees, so it should not look like a different product.
    No logo image on purpose: this page is served before the cookie exists, so
    an image request would hit this same gate and come back as HTML. */
 :root{--org:#ff650a;--ink:#090a0b;--white:#f2f2ed;--mut:#a4a5a7;--edge:#ffffff26}
 *{box-sizing:border-box}
 body{margin:0;min-height:100svh;display:flex;align-items:center;justify-content:center;padding:26px;
   background:var(--ink);color:var(--white);font-family:'DM Sans',Arial,sans-serif}
 ::selection{background:var(--org);color:#080808}
 .box{width:100%;max-width:392px}
 .mark{font-family:'Barlow Condensed','Arial Narrow',sans-serif;font-weight:700;
   letter-spacing:.07em;font-size:30px;text-transform:uppercase;line-height:1}
 .mark b{color:var(--org);font-weight:700}
 .sub{color:var(--mut);font-size:11.5px;letter-spacing:.16em;text-transform:uppercase;
   font-weight:600;margin:10px 0 34px}
 label{display:block;font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;
   color:var(--mut);font-weight:600;margin-bottom:9px}
 input{width:100%;padding:14px 15px;background:#ffffff08;border:1px solid var(--edge);border-radius:3px;
   color:var(--white);font-size:16px;font-family:inherit}
 input:focus{outline:none;border-color:var(--org);background:#ffffff0d}
 button{width:100%;margin-top:14px;padding:15px;min-height:48px;background:var(--org);border:0;
   border-radius:3px;color:#080808;font-family:'DM Sans',Arial,sans-serif;font-weight:700;
   font-size:12.5px;letter-spacing:.1em;text-transform:uppercase;cursor:pointer}
 button:hover{background:#ff7a2e}
 .err{margin-top:14px;color:var(--org);font-size:13px}
 .foot{margin-top:28px;color:var(--mut);font-size:12px;line-height:1.65;
   border-top:1px solid #ffffff13;padding-top:18px}
</style></head><body>
<form class="box" method="POST">
  <div class="mark">EVER<b>GUARD</b></div>
  <div class="sub">Private preview</div>
  <label for="p">Access code</label>
  <input id="p" name="password" type="password" autocomplete="current-password" autofocus>
  <button type="submit">Enter</button>
  ${error ? '<div class="err">That code did not work. Try again.</div>' : ""}
  <div class="foot">Private material. If you need the code, ask the person who sent you the link.</div>
</form></body></html>`,
    { status: error ? 401 : 401, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } }
  );
}

export default async function gate(request: Request, context: any) {
  const secret = Deno.env.get("DECK_PASSWORD");
  if (!secret) {
    // Fail CLOSED. This used to call context.next(), which meant a cleared or
    // missing environment variable silently served the whole private proposal
    // to anyone who asked. For client material, dark is better than naked.
    return new Response(
      "Temporarily unavailable. Ask the person who sent you the link.",
      { status: 503, headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" } }
    );
  }

  const good = await token(secret);

  if (request.method === "POST") {
    const form = await request.formData();
    const given = String(form.get("password") ?? "");
    if ((await token(given)) === good) {
      const headers = new Headers({ location: new URL(request.url).pathname });
      headers.append(
        "set-cookie",
        `${COOKIE}=${good}; Path=/; Max-Age=${MAX_AGE}; HttpOnly; Secure; SameSite=Lax`
      );
      return new Response(null, { status: 303, headers });
    }
    return page(true);
  }

  const cookie = request.headers.get("cookie") ?? "";
  const has = cookie.split(";").some(c => c.trim() === `${COOKIE}=${good}`);
  return has ? context.next() : page(false);
}

export const config = { path: "/*" };
