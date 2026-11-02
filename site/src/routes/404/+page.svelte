<script>
	// prerendered to 404.html, which github pages serves for any address it can't find
	import { asset, resolve } from '$app/paths';
	import '../../app.css';
</script>

<svelte:head>
	<title>not found · fixpoint</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<header class="masthead">
	<span><a href="https://github.com/oddurs">oddurs</a> &rsaquo; <a href={resolve('/')}>fixpoint</a></span>
	<span
		>[ <a href={asset('/fixpoint.bmp')} download>fixpoint.bmp</a> |
		<a href="https://github.com/oddurs/fixpoint">source</a> ]</span
	>
</header>

<main>
	<header class="post">
		<h1><span class="tt">404</span>: not found</h1>
	</header>
	<p class="lead">nothing lives at this address: not a picture, not a disk, not an archive.</p>
	<p><a href={resolve('/')}>back to fixpoint</a></p>
</main>
