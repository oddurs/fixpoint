<script>
	import 'github-markdown-css/github-markdown.css';
	import '../app.css';
	import { asset } from '$app/paths';

	let { data } = $props();

	const repo = 'https://github.com/oddurs/fixpoint';
	const site = 'https://oddurs.github.io/fixpoint';
	const title = 'fixpoint — a 66 KB image that boots and computes itself';
	const description =
		'A 320×200 BMP that is also a boot sector. Boot it and the CPU recomputes the picture: Rule 110, seeded by its own machine code.';
</script>

<svelte:head>
	<title>{title}</title>
	<meta name="description" content={description} />
	<meta property="og:title" content={title} />
	<meta property="og:description" content={description} />
	<meta property="og:image" content="{site}/poster.png" />
	<meta property="og:url" content={site} />
	<meta name="twitter:card" content="summary_large_image" />
</svelte:head>

<main>
	<nav>
		<a class="repo" href={repo}><span class="owner">oddurs</span> / <strong>fixpoint</strong></a>
		<span class="actions">
			<a class="btn" href={asset('/fixpoint.bmp')} download>download fixpoint.bmp</a>
			<a class="btn" href={repo}>source</a>
		</span>
	</nav>

	<div class="box">
		<div class="box-header">README.md</div>
		<article class="markdown-body">
			<video
				src={asset('/demo.mp4')}
				poster={asset('/poster.png')}
				autoplay
				muted
				loop
				playsinline
				controls
				width="960"
				height="600"
				aria-label="fixpoint.bmp opened as an image, then booted in qemu, where it recomputes the same picture"
			></video>
			{@html data.html}
		</article>
	</div>
</main>
