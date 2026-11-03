// the date git last touched a path, for the page's byline and the sitemap. the pages
// workflow fetches full history. a path with no history yet is new: it was last touched
// now. a git failure fails the build.

import { execSync } from 'node:child_process';

export const root = process.cwd() + '/../'; // the build runs in site/

export function touched(path, format = '%cI') {
	const out = execSync(`git log -1 --format=${format} -- ${path}`, { cwd: root }).toString().trim();
	return out || new Date().toISOString();
}
