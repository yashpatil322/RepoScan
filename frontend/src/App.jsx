import { Routes, Route } from 'react-router-dom'
import NavBar from './components/NavBar.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Ingest from './pages/Ingest.jsx'
import Ask from './pages/Ask.jsx'
import Search from './pages/Search.jsx'
import Repos from './pages/Repos.jsx'

export default function App() {
  return (
    <div className="min-h-screen relative">
      <div className="fixed inset-0 bg-grain pointer-events-none z-[1] mix-blend-overlay" />
      <NavBar />
      <main className="relative z-[2] pb-24 md:pb-0">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/ingest" element={<Ingest />} />
          <Route path="/ask" element={<Ask />} />
          <Route path="/search" element={<Search />} />
          <Route path="/repos" element={<Repos />} />
        </Routes>
      </main>
    </div>
  )
}
