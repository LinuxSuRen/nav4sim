package main

// nav4sim web control — a small web UI to pick and (re)start simulation worlds.
//
// Endpoints:
//
//	GET  /            — control page (world dropdown, spawn point, GUI switch)
//	GET  /api/worlds  — list available world files
//	GET  /api/status  — current simulation status (running world, pid, uptime)
//	POST /api/start   — (re)start simulation with {"world":..., "spawn_x":..., "spawn_y":..., "gui":bool}
//	POST /api/stop    — stop the running simulation
//
// Environment:
//
//	NAV4SIM_WEB_PORT  — listen port (default 8080)
//	NAV4SIM_GZ_DIR    — install root containing launch/ and worlds/ (default /opt/gz)
//	NAV4SIM_AUTOSTART — set to "false" to not launch the default world on boot
//	NAV4SIM_ROS_SETUP — ROS setup.bash to source (default /opt/ros/humble/setup.bash)
import (
	"encoding/json"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"sync"
	"syscall"
	"time"
)

var (
	webPort   = envOr("NAV4SIM_WEB_PORT", "8080")
	gzDir     = envOr("NAV4SIM_GZ_DIR", "/opt/gz")
	rosSetup  = envOr("NAV4SIM_ROS_SETUP", "/opt/ros/humble/setup.bash")
	autoStart = os.Getenv("NAV4SIM_AUTOSTART") != "false"

	worldsDir    = filepath.Join(gzDir, "worlds")
	launchFile   = filepath.Join(gzDir, "launch", "gz.launch.py")
	defaultWorld = "explore_room.world"
)

type simState struct {
	mu        sync.Mutex
	cmd       *exec.Cmd
	world     string
	startedAt time.Time
}

var state simState

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func listWorlds() []string {
	matches, err := filepath.Glob(filepath.Join(worldsDir, "*.world"))
	if err != nil || len(matches) == 0 {
		return []string{defaultWorld}
	}
	names := make([]string, 0, len(matches))
	for _, m := range matches {
		names = append(names, filepath.Base(m))
	}
	sort.Strings(names)
	return names
}

// stop terminates the running simulation (the whole process group, so the
// gazebo children of `ros2 launch` die too). Idempotent.
func (s *simState) stop() {
	if s.cmd == nil || s.cmd.Process == nil {
		s.cmd, s.world, s.startedAt = nil, "", time.Time{}
		return
	}
	// negative pid = signal the whole process group
	_ = syscall.Kill(-s.cmd.Process.Pid, syscall.SIGTERM)
	done := make(chan struct{})
	go func() { _, _ = s.cmd.Process.Wait(); close(done) }()
	select {
	case <-done:
	case <-time.After(10 * time.Second):
		_ = syscall.Kill(-s.cmd.Process.Pid, syscall.SIGKILL)
		<-done
	}
	s.cmd, s.world, s.startedAt = nil, "", time.Time{}
}

func (s *simState) start(world, spawnX, spawnY string, gui bool) error {
	s.stop()
	script := fmt.Sprintf("source %s && exec ros2 launch %s world:=%s spawn_x:=%s spawn_y:=%s gui:=%t",
		rosSetup, launchFile, world, spawnX, spawnY, gui)
	cmd := exec.Command("bash", "-c", script)
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if err := cmd.Start(); err != nil {
		return err
	}
	s.cmd, s.world, s.startedAt = cmd, world, time.Now()
	return nil
}

func (s *simState) status() (running bool, world string, uptime float64) {
	running = s.cmd != nil && s.cmd.Process != nil &&
		s.cmd.ProcessState == nil // non-nil only after Wait(); we never Wait in the handler path
	// re-check liveness: signal 0 fails on a dead (but unreaped) child only after exit
	if running {
		if err := syscall.Kill(-s.cmd.Process.Pid, 0); err != nil {
			running = false
		}
	}
	if running {
		world = s.world
		uptime = time.Since(s.startedAt).Seconds()
	}
	return
}

var pageTpl = template.Must(template.New("page").Parse(`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>nav4sim</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 480px; margin: 48px auto; padding: 0 16px; }
  h1 { font-size: 1.4rem; }
  label { display: block; margin-top: 12px; font-size: .9rem; color: #555; }
  select, input { width: 100%; padding: 8px; margin-top: 4px; box-sizing: border-box; font-size: 1rem; }
  .row { display: flex; gap: 12px; }
  button { margin-top: 20px; padding: 10px 24px; font-size: 1rem; cursor: pointer; }
  #stop { background: #fff; }
  #status { margin-top: 24px; font-size: .9rem; color: #333; min-height: 1.2em; }
</style>
</head>
<body>
<h1>nav4sim — simulation control</h1>
<label>World
<select id="world"></select>
</label>
<div class="row">
  <div style="flex:1"><label>Spawn X<input id="spawn_x" type="number" step="0.1" value="-12.0"></label></div>
  <div style="flex:1"><label>Spawn Y<input id="spawn_y" type="number" step="0.1" value="0.0"></label></div>
</div>
<label><input type="checkbox" id="gui" style="width:auto"> Gazebo GUI</label>
<div>
  <button id="start">Start / Switch</button>
  <button id="stop">Stop</button>
</div>
<p id="status"></p>
<script>
const $ = id => document.getElementById(id);
async function refresh() {
  const s = await (await fetch('/api/status')).json();
  const opt = s.worlds.map(w =>
    '<option' + (w === s.world ? ' selected' : '') + '>' + w + '</option>').join('');
  $('world').innerHTML = opt;
  $('status').textContent = s.running
    ? 'Running: ' + s.world + ' (uptime ' + Math.round(s.uptime) + 's)'
    : 'Simulation stopped';
}
$('start').onclick = async () => {
  $('status').textContent = 'Starting…';
  const r = await (await fetch('/api/start', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({world: $('world').value, spawn_x: $('spawn_x').value,
      spawn_y: $('spawn_y').value, gui: $('gui').checked})})).json();
  if (r.error) $('status').textContent = 'Error: ' + r.error;
  setTimeout(refresh, 1500);
};
$('stop').onclick = async () => {
  await fetch('/api/stop', {method: 'POST'});
  setTimeout(refresh, 500);
};
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
`))

func writeJSON(w http.ResponseWriter, code int, obj any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(obj)
}

func main() {
	if autoStart {
		state.mu.Lock()
		if err := state.start(defaultWorld, "-12.0", "0.0", false); err != nil {
			log.Printf("[web] autostart failed: %v", err)
		}
		state.mu.Unlock()
	}

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			writeJSON(w, http.StatusNotFound, map[string]string{"error": "not found"})
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_ = pageTpl.Execute(w, nil)
	})
	http.HandleFunc("GET /api/worlds", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{"worlds": listWorlds()})
	})
	http.HandleFunc("GET /api/status", func(w http.ResponseWriter, r *http.Request) {
		state.mu.Lock()
		running, world, uptime := state.status()
		state.mu.Unlock()
		writeJSON(w, http.StatusOK, map[string]any{
			"running": running, "world": world, "uptime": uptime, "worlds": listWorlds(),
		})
	})
	http.HandleFunc("POST /api/start", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			World  string  `json:"world"`
			SpawnX float64 `json:"spawn_x"`
			SpawnY float64 `json:"spawn_y"`
			Gui    bool    `json:"gui"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
			return
		}
		if req.World == "" {
			req.World = defaultWorld
		}
		valid := false
		for _, wld := range listWorlds() {
			if wld == req.World {
				valid = true
				break
			}
		}
		if !valid {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "unknown world: " + req.World})
			return
		}
		state.mu.Lock()
		err := state.start(req.World, fmt.Sprintf("%.1f", req.SpawnX), fmt.Sprintf("%.1f", req.SpawnY), req.Gui)
		world := req.World
		state.mu.Unlock()
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"started": world})
	})
	http.HandleFunc("POST /api/stop", func(w http.ResponseWriter, r *http.Request) {
		state.mu.Lock()
		state.stop()
		state.mu.Unlock()
		writeJSON(w, http.StatusOK, map[string]bool{"stopped": true})
	})

	addr := "0.0.0.0:" + webPort
	log.Printf("[web] nav4sim control UI on http://%s", addr)
	if err := http.ListenAndServe(addr, nil); err != nil {
		log.Fatal(err)
	}
}
