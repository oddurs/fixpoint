<script>
	import '../app.css';
	import { asset } from '$app/paths';

	let { data } = $props();

	const repo = 'https://github.com/oddurs/fixpoint';
	const site = 'https://oddurs.github.io/fixpoint';
	const title = 'fixpoint: an image that boots and computes itself';
	const description =
		'a picture of its own consequences. a 320×200 bmp that is also a boot sector: boot it and it draws itself again. rule 110, its ether, and the light cone of a program hiding in the top row.';
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

<div class="masthead">
	<span><a href="https://github.com/oddurs">oddurs</a> &rsaquo; fixpoint</span>
	<span>[ <a href={asset('/fixpoint.bmp')} download>fixpoint.bmp</a> | <a href={repo}>source</a> ]</span>
</div>

<main>
	<header class="maketitle">
		<h1><span class="tt">fixpoint</span>: an image that boots and computes itself</h1>
		<p class="author">Oddur Sigurdsson</p>
		<p class="date">{data.date}</p>
	</header>

	<blockquote class="epigraph">{data.epigraph}</blockquote>

	<section class="abstract">
		<h2>Abstract</h2>
		<p>{@html data.abstract}</p>
	</section>

	<figure class="wide">
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
		<figcaption>
			<b>Figure 0.</b> <span class="tt">fixpoint.bmp</span>, opened as an image, then booted in QEMU,
			where it computes the same picture again. Every frame of the computation is the real screen,
			paused under <span class="tt">gdb</span> every two rows. (<a href={asset('/demo.mp4')}>MP4</a>,
			{data.video}.)
		</figcaption>
	</figure>

	<p class="noindent">To try it yourself:</p>
	<pre class="commands">{data.commands}</pre>

	<nav class="contents">
		<h2>Contents</h2>
		<ol>
			{#each data.toc as s (s.id)}
				<li class="level{s.level}"><span class="num">{s.num}</span><a href="#{s.id}">{@html s.text}</a></li>
			{/each}
			<li class="level2"><span class="num">A</span><a href="#files">files</a></li>
			<li class="level2"><span class="num">B</span><a href="#citing">citing this</a></li>
		</ol>
	</nav>

	<article class="paper">
		{@html data.html}

		<h2 id="files" class="appendix"><span class="secnum">A</span>files</h2>
		<table class="listing">
			<thead>
				<tr><th>Name</th><th>Last modified</th><th class="r">Size</th><th>Description</th></tr>
			</thead>
			<tbody>
				{#each data.files as f (f.name)}
					<tr>
						<td class="tt"><a href={f.href.startsWith('http') ? f.href : asset('/' + f.href)}>{f.name}</a></td>
						<td class="tt">{f.date}</td>
						<td class="tt r">{f.size}</td>
						<td>{f.what}</td>
					</tr>
				{/each}
			</tbody>
		</table>

		<h2 id="citing" class="appendix"><span class="secnum">B</span>citing this</h2>
		<p>if, for some reason, you need to:</p>
		<pre class="bibtex">@misc&#123;sigurdsson2026fixpoint,
  author       = &#123;Oddur Sigurdsson&#125;,
  title        = &#123;&#123;fixpoint&#125;: an image that boots and computes itself&#125;,
  year         = &#123;2026&#125;,
  howpublished = &#123;\url&#123;{site}&#125;&#125;,
  note         = &#123;source: \url&#123;{repo}&#125;&#125;
&#125;</pre>
	</article>

	<footer>
		<hr />
		<p>
			Last modified: <span class="tt">{data.modified}</span><br />
			<span class="tt">fixpoint.bmp</span> is {data.bmp} bytes and <a href="{repo}/blob/main/LICENSE">MIT</a>
			licensed. This page has no JavaScript and no cookies. It is set in
			<a href="{repo}/tree/main/site/src/fonts">Latin Modern</a>.
		</p>
	</footer>
</main>
