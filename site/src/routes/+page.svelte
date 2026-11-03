<script>
	import '../app.css';
	import { asset } from '$app/paths';
	import roman from '../fonts/fp-lmroman10-regular.woff2?url';

	let { data } = $props();

	const repo = 'https://github.com/oddurs/fixpoint';
	const commands = ['qemu-system-i386 -drive format=raw,file=fixpoint.bmp', 'unzip fixpoint.bmp'];
	const site = 'https://fixpoint.oddurs.com/';
	const title = 'fixpoint: an image that boots and computes itself';
	// 155 characters: the most a search result shows whole
	const description =
		'a 320×200 bmp that is also a boot sector. boot it and the cpu draws the same picture again: rule 110, seeded by the 130-byte program hiding in its top row.';
	const author = { '@type': 'Person', name: 'Oddur Sigurdsson', url: 'https://github.com/oddurs' };
	// the link preview is cut from fixpoint.bmp by demo/figures.py
	const social = {
		url: `${site}social.png`,
		width: 1200,
		height: 630,
		alt: 'fixpoint.bmp magnified: a dark V of woven ether between two coral and plum cones of rule 110 triangles, with the program’s own row along the top edge'
	};

	// structured data: a post about a piece of source code, by whom, under what license
	const ld = {
		'@context': 'https://schema.org',
		'@graph': [
			{
				'@type': 'BlogPosting',
				'@id': `${site}#post`,
				headline: title,
				description,
				url: site,
				mainEntityOfPage: site,
				image: social.url,
				inLanguage: 'en',
				author,
				datePublished: data.published,
				dateModified: data.iso,
				about: { '@id': `${site}#code` }
			},
			{
				'@type': 'SoftwareSourceCode',
				'@id': `${site}#code`,
				name: 'fixpoint',
				description,
				url: site,
				image: social.url,
				codeRepository: repo,
				programmingLanguage: ['Assembly', 'Python'],
				license: 'https://opensource.org/licenses/MIT',
				author,
				dateModified: data.iso
			}
		]
	};
	const jsonld = `<script type="application/ld+json">${JSON.stringify(ld).replace(/</g, '\\u003c')}</` + 'script>';
</script>

<svelte:head>
	<title>{title}</title>
	<meta name="description" content={description} />
	<meta name="author" content="Oddur Sigurdsson" />
	<meta name="robots" content="index, follow, max-image-preview:large" />
	<meta name="theme-color" content="#0a0c16" />
	<link rel="canonical" href={site} />
	<link rel="preload" href={roman} as="font" type="font/woff2" crossorigin="anonymous" />

	<meta property="og:type" content="article" />
	<meta property="og:locale" content="en_US" />
	<meta property="og:site_name" content="fixpoint" />
	<meta property="og:title" content={title} />
	<meta property="og:description" content={description} />
	<meta property="og:url" content={site} />
	<meta property="og:image" content={social.url} />
	<meta property="og:image:type" content="image/png" />
	<meta property="og:image:width" content={social.width} />
	<meta property="og:image:height" content={social.height} />
	<meta property="og:image:alt" content={social.alt} />
	<meta property="article:published_time" content={data.published} />
	<meta property="article:modified_time" content={data.iso} />
	<meta property="article:author" content={author.url} />
	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:title" content={title} />
	<meta name="twitter:description" content={description} />
	<meta name="twitter:image" content={social.url} />
	<meta name="twitter:image:alt" content={social.alt} />

	<!-- eslint-disable-next-line svelte/no-at-html-tags -- built here from constants, < escaped -->
	{@html jsonld}
</svelte:head>

<header class="masthead">
	<span><a href="https://github.com/oddurs">oddurs</a> &rsaquo; fixpoint</span>
	<span>[ <a href={asset('/fixpoint.bmp')} download>fixpoint.bmp</a> | <a href={repo}>source</a> ]</span>
</header>

<main>
	<header class="post">
		<h1><span class="tt">fixpoint</span>: an image that boots and computes itself</h1>
		<p class="byline">oddur sigurdsson &middot; <time datetime={data.published}>{data.date}</time></p>
		<p class="tagline">a picture of its own consequences.</p>
	</header>

	<p class="lead">
		<a href={asset('/fixpoint.bmp')} class="tt">fixpoint.bmp</a> is a normal 320&times;200 bitmap. open it in anything and
		it&rsquo;s just a picture. write it to a disk and boot it, and the computer draws the exact same picture again, byte for
		byte, without looking at it. unzip it and you get its source code. the pattern is rule 110, and the colourful part is
		everywhere that 130 bytes of code, hidden in the top row, have managed to reach so far.
	</p>
	<p class="aside">here it is, booting:</p>

	<figure class="wide">
		<video
			src={asset('/demo.mp4')}
			poster={asset('/poster.png')}
			width="960"
			height="600"
			autoplay
			muted
			loop
			playsinline
			controls
			aria-label="fixpoint.bmp opened as an image, then booted in qemu, where it recomputes the same picture"
		></video>
		<figcaption>
			opened as an image, then booted in qemu. every frame of the computation is the real screen, paused under
			<span class="tt">gdb</span> every two rows. (<a href={asset('/demo.mp4')}>mp4</a>, {data.video})
		</figcaption>
	</figure>

	<p class="aside">if you want to try it:</p>
	<pre class="commands">{#each commands as line, i (i)}<span class="prompt" aria-hidden="true"
				>$ </span>{line}{'\n'}{/each}</pre>

	<article class="body">
		<!-- eslint-disable-next-line svelte/no-at-html-tags -- site/src/post.md, rendered at build time -->
		{@html data.html}
	</article>

	<footer>
		<hr />
		<p>
			last modified <time class="tt" datetime={data.iso}>{data.modified}</time><br />
			<span class="tt">fixpoint.bmp</span> is {data.bmp} bytes and <a href="{repo}/blob/main/LICENSE">mit</a>
			licensed. this page has no javascript and no cookies. it&rsquo;s set in
			<a href="{repo}/tree/main/site/src/fonts">latin modern</a>.
		</p>
	</footer>
</main>
