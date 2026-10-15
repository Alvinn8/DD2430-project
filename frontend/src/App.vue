<template>
  <nav>
    <router-link to="/">Home</router-link> |
    <router-link to="/about">About</router-link>
  </nav>

  <router-view />
</template>

<style>
nav {
  padding: 20px;
}
nav a {
  margin-right: 10px;
  text-decoration: none;
}
nav a.router-link-exact-active {
  font-weight: bold;
}
</style>
