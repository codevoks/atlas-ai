export async function GET(): Promise<Response> {
  return Response.json({ status: "healthy", service: "atlas-web" });
}

