require('dotenv').config();
const express = require('express');
const cors = require('cors');
const axios = require('axios');

const app = express();
const PORT = process.env.PORT || 3000;

// Allow your frontend to talk to this backend
app.use(cors());
app.use(express.json());

// Store data in memory
let playersCache = [];
let statsCache = {};

// =======================
// HELPER FUNCTIONS
// =======================

// Get NFL players from ESPN (free API)
async function getNFLPlayers() {
  try {
    const response = await axios.get(
      'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams'
    );
    
    const players = [];
    const teams = response.data.sports[0].leagues[0].teams.slice(0, 5); // Just 5 teams for demo
    
    for (const teamData of teams) {
      const team = teamData.team;
      // Add sample players
      players.push({
        id: `nfl-${team.id}01`,
        name: `QB ${team.location}`,
        team: team.abbreviation,
        position: 'QB',
        sport: 'NFL'
      });
      players.push({
        id: `nfl-${team.id}02`,
        name: `RB ${team.location}`,
        team: team.abbreviation,
        position: 'RB',
        sport: 'NFL'
      });
    }
    
    return players;
  } catch (error) {
    console.log('Using sample NFL data');
    // Return sample data if API fails
    return [
      { id: 'nfl-1', name: 'Patrick Mahomes', team: 'KC', position: 'QB', sport: 'NFL' },
      { id: 'nfl-2', name: 'Josh Allen', team: 'BUF', position: 'QB', sport: 'NFL' },
      { id: 'nfl-3', name: 'Christian McCaffrey', team: 'SF', position: 'RB', sport: 'NFL' },
      { id: 'nfl-4', name: 'Tyreek Hill', team: 'MIA', position: 'WR', sport: 'NFL' },
      { id: 'nfl-5', name: 'Travis Kelce', team: 'KC', position: 'TE', sport: 'NFL' }
    ];
  }
}

// Get NBA players from Ball Don't Lie (free API)
async function getNBAPlayers() {
  try {
    const response = await axios.get(
      'https://www.balldontlie.io/api/v1/players?per_page=10'
    );
    
    return response.data.data
      .filter(p => p.team)
      .map(p => ({
        id: `nba-${p.id}`,
        name: `${p.first_name} ${p.last_name}`,
        team: p.team.abbreviation,
        position: p.position || 'F',
        sport: 'NBA'
      }));
  } catch (error) {
    console.log('Using sample NBA data');
    // Return sample data if API fails
    return [
      { id: 'nba-1', name: 'LeBron James', team: 'LAL', position: 'F', sport: 'NBA' },
      { id: 'nba-2', name: 'Stephen Curry', team: 'GSW', position: 'G', sport: 'NBA' },
      { id: 'nba-3', name: 'Kevin Durant', team: 'PHX', position: 'F', sport: 'NBA' },
      { id: 'nba-4', name: 'Giannis Antetokounmpo', team: 'MIL', position: 'F', sport: 'NBA' },
      { id: 'nba-5', name: 'Nikola Jokic', team: 'DEN', position: 'C', sport: 'NBA' }
    ];
  }
}

// Get sample NHL players
function getNHLPlayers() {
  return [
    { id: 'nhl-1', name: 'Connor McDavid', team: 'EDM', position: 'C', sport: 'NHL' },
    { id: 'nhl-2', name: 'Auston Matthews', team: 'TOR', position: 'C', sport: 'NHL' },
    { id: 'nhl-3', name: 'Nathan MacKinnon', team: 'COL', position: 'C', sport: 'NHL' }
  ];
}

// Get sample MLB players
function getMLBPlayers() {
  return [
    { id: 'mlb-1', name: 'Mike Trout', team: 'LAA', position: 'CF', sport: 'MLB' },
    { id: 'mlb-2', name: 'Mookie Betts', team: 'LAD', position: 'RF', sport: 'MLB' },
    { id: 'mlb-3', name: 'Shohei Ohtani', team: 'LAA', position: 'P', sport: 'MLB' }
  ];
}

// Generate sample stats
function generateStats(players) {
  const stats = {};
  
  players.forEach(player => {
    if (player.sport === 'NFL') {
      if (player.position === 'QB') {
        stats[player.id] = {
          passing_yards: 3500 + Math.floor(Math.random() * 1500),
          td_thrown: 25 + Math.floor(Math.random() * 15),
          interceptions: 8 + Math.floor(Math.random() * 7),
          rushing_yards: 200 + Math.floor(Math.random() * 200),
          rushing_td: 2 + Math.floor(Math.random() * 3)
        };
      } else if (player.position === 'RB') {
        stats[player.id] = {
          rushing_yards: 800 + Math.floor(Math.random() * 700),
          rushing_td: 6 + Math.floor(Math.random() * 8),
          receiving_yards: 300 + Math.floor(Math.random() * 300),
          receiving_td: 2 + Math.floor(Math.random() * 3),
          receptions: 30 + Math.floor(Math.random() * 30)
        };
      } else {
        stats[player.id] = {
          receiving_yards: 700 + Math.floor(Math.random() * 600),
          receiving_td: 5 + Math.floor(Math.random() * 7),
          receptions: 50 + Math.floor(Math.random() * 40)
        };
      }
    } else if (player.sport === 'NBA') {
      stats[player.id] = {
        points: 1200 + Math.floor(Math.random() * 1000),
        assists: 200 + Math.floor(Math.random() * 400),
        rebounds: 300 + Math.floor(Math.random() * 500),
        blocks: 30 + Math.floor(Math.random() * 50),
        steals: 50 + Math.floor(Math.random() * 50)
      };
    } else if (player.sport === 'NHL') {
      stats[player.id] = {
        goals: 20 + Math.floor(Math.random() * 30),
        assists: 30 + Math.floor(Math.random() * 40),
        points: 50 + Math.floor(Math.random() * 60),
        plus_minus: -5 + Math.floor(Math.random() * 30),
        penalty_minutes: 20 + Math.floor(Math.random() * 40)
      };
    } else if (player.sport === 'MLB') {
      stats[player.id] = {
        batting_avg: 0.250 + Math.random() * 0.080,
        home_runs: 15 + Math.floor(Math.random() * 25),
        rbi: 50 + Math.floor(Math.random() * 50),
        runs: 60 + Math.floor(Math.random() * 40),
        stolen_bases: 5 + Math.floor(Math.random() * 20)
      };
    }
  });
  
  return stats;
}

// Load all data on startup
async function loadData() {
  console.log('Loading player data...');
  
  const [nflPlayers, nbaPlayers] = await Promise.all([
    getNFLPlayers(),
    getNBAPlayers()
  ]);
  
  const nhlPlayers = getNHLPlayers();
  const mlbPlayers = getMLBPlayers();
  
  playersCache = [...nflPlayers, ...nbaPlayers, ...nhlPlayers, ...mlbPlayers];
  statsCache = generateStats(playersCache);
  
  console.log(`Loaded ${playersCache.length} players`);
}

// =======================
// API ENDPOINTS (What your frontend needs)
// =======================

// Health check - visit this to see if your backend is working
app.get('/', (req, res) => {
  res.json({ 
    message: 'OmniFantasy Backend is running!',
    endpoints: ['/api/players', '/api/stats'],
    totalPlayers: playersCache.length
  });
});

// Get all players - YOUR FRONTEND NEEDS THIS
app.get('/api/players', (req, res) => {
  res.json(playersCache);
});

// Get all stats - YOUR FRONTEND NEEDS THIS
app.get('/api/stats', (req, res) => {
  res.json(statsCache);
});

// =======================
// START THE SERVER
// =======================

loadData().then(() => {
  app.listen(PORT, () => {
    console.log('');
    console.log('🎉 SUCCESS! Your backend is running!');
    console.log('================================');
    console.log(`📍 Local URL: http://localhost:${PORT}`);
    console.log(`📊 Players endpoint: http://localhost:${PORT}/api/players`);
    console.log(`📈 Stats endpoint: http://localhost:${PORT}/api/stats`);
    console.log('================================');
    console.log('');
  });
});
