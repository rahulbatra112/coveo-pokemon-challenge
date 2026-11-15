// Shared settings for index.html (search page) and pokemon.html (detail page).
//
// accessToken is the public "Anonymous search" API key, locked to the "Pokedex"
// search hub. It can only run queries and send usage analytics, so it is safe
// in browser code and in a public repository. Never put a private key here.
window.POKEDEX_CONFIG = {
  organizationId: "69ydoe1s4lcvoorg",
  accessToken: "xxd67fea27-1baa-4ff2-8ca1-6da22acea028",
  searchHub: "Pokedex",
};
