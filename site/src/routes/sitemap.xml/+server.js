// one page, with the date it last changed, so crawlers know when to come back
import { touched } from '../../lib/touched.js';

export const prerender = true;

export function GET() {
	const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
	<url>
		<loc>https://fixpoint.oddurs.com/</loc>
		<lastmod>${touched('.')}</lastmod>
	</url>
</urlset>
`;
	return new Response(xml, { headers: { 'content-type': 'application/xml' } });
}
