<script>
	import '../app.css';
	import { asset } from '$app/paths';
	import roman from '../fonts/fp-lmroman10-regular.woff2?url';

	let { data } = $props();

	const repo = 'https://github.com/oddurs/fixpoint';
	const commands = ['qemu-system-i386 -drive format=raw,file=fixpoint.bmp', 'unzip fixpoint.bmp'];
	const site = 'https://fixpoint.oddurs.com/';
	const title = 'fixpoint: an image that boots and computes itself';
	const description =
		'a 320×200 bmp that is also a boot sector. boot it and the cpu draws the same picture again: rule 110 in its ether, and the light cone of the 130-byte program hiding in its top row.';
	const poster = { url: `${site}poster.png`, width: 960, height: 600 };

	// structured data, so search engines know this is source code, by whom, under what license
	const ld = {
		'@context': 'https://schema.org',
		'@type': 'SoftwareSourceCode',
		name: 'fixpoint',
		headline: title,
		description,
		url: site,
		image: poster.url,
		codeRepository: repo,
		programmingLanguage: ['Assembly', 'Python'],
		license: 'https://opensource.org/licenses/MIT',
		author: { '@type': 'Person', name: 'Oddur Sigurdsson', url: 'https://github.com/oddurs' },
		dateModified: data.iso
	};
	const jsonld = `<script type="application/ld+json">${JSON.stringify(ld).replace(/</g, '\\u003c')}</` + 'script>';
</script>

<svelte:head>
	<title>{title}</title>
	<meta name="description" content={description} />
	<meta name="author" content="Oddur Sigurdsson" />
	<link rel="canonical" href={site} />
	<link rel="preload" href={roman} as="font" type="font/woff2" crossorigin="anonymous" />

	<meta property="og:type" content="website" />
	<meta property="og:site_name" content="fixpoint" />
	<meta property="og:title" content={title} />
	<meta property="og:description" content={description} />
	<meta property="og:url" content={site} />
	<meta property="og:image" content={poster.url} />
	<meta property="og:image:width" content={poster.width} />
	<meta property="og:image:height" content={poster.height} />
	<meta property="og:image:alt" content="a dark V of woven pattern between two bright cones of rule 110 triangles" />
	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:title" content={title} />
	<meta name="twitter:description" content={description} />
	<meta name="twitter:image" content={poster.url} />

	{@html jsonld}
</svelte:head>

<header class="masthead">
	<span><a href="https://github.com/oddurs">oddurs</a> &rsaquo; fixpoint</span>
	<span>[ <a href={asset('/fixpoint.bmp')} download>fixpoint.bmp</a> | <a href={repo}>source</a> ]</span>
</header>

<main>
	<header class="post">
		<h1><span class="tt">fixpoint</span>: an image that boots and computes itself</h1>
		<p class="byline">oddur sigurdsson &middot; <time datetime={data.iso}>{data.date}</time></p>
		<p class="tagline">a picture of its own consequences.</p>
	</header>

	<p class="lead">
		<a href={asset('/fixpoint.bmp')} class="tt">fixpoint.bmp</a> is an ordinary 320&times;200 bitmap: open it in anything and it&rsquo;s an image. write it to a disk and boot it, and
		the cpu draws the same image again, byte for byte, without looking. unzip it and it hands you its own source. the
		picture is rule 110 running through its ether, disturbed by 130 bytes of code hiding in the top row, and what
		you&rsquo;re looking at is that code&rsquo;s light cone: everywhere its influence has reached so far.
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
	<pre class="commands">{#each commands as line, i (i)}<span class="prompt" aria-hidden="true">$ </span>{line}{'\n'}{/each}</pre>

	<article class="body">
		{@html data.html}

		<h2 id="the-files">the files</h2>
		<table class="listing">
			<thead>
				<tr><th scope="col">name</th><th scope="col">last modified</th><th scope="col" class="r">size</th><th scope="col">what it is</th></tr>
			</thead>
			<tbody>
				{#each data.files as f (f.name)}
					<tr>
						<td class="tt"><a href={f.href.startsWith('http') ? f.href : asset('/' + f.href)}>{f.name}</a></td>
						<td class="tt"><time datetime={f.date}>{f.date}</time></td>
						<td class="tt r">{f.size}</td>
						<td>{f.what}</td>
					</tr>
				{/each}
			</tbody>
		</table>
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
