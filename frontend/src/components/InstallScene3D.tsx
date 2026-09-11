import { useEffect, useRef } from "react";
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";

// A low-poly 3D "product shot" of the full AquaReserve install, sitting in the hero: 
//  - a water reserve,
//  - a solar LoRaWAN gateway,
//  - a per-zone control node and
//  - three field beds.
// It holds a flattering 3/4 angle, breathes gently and can be dragged to spin.
// Three.js is bundled (no CDN), transparent background so it floats on white.
export default function InstallScene3D() {
  const mount = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = mount.current!;

    const scene = new THREE.Scene();
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(renderer.domElement);

    const viewSize = 9;
    const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 100);

    cam.position.set(7, 6, 9);
    cam.lookAt(0, 1, 0);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x93a9b8, 1.0));

    const key = new THREE.DirectionalLight(0xffffff, 1.1);

    key.position.set(6, 11, 7);

    scene.add(key);
    scene.add(new THREE.AmbientLight(0xffffff, 0.2));

    const model = new THREE.Group();

    scene.add(model);

    const mat = (color: number, opts: Partial<THREE.MeshStandardMaterialParameters> = {}) =>
      new THREE.MeshStandardMaterial({ color, roughness: 0.78, metalness: 0.05, flatShading: true, ...opts });

    const add = (geo: THREE.BufferGeometry, m: THREE.Material | THREE.Material[], x: number, y: number, z: number) => {
      const mesh = new THREE.Mesh(geo, m);

      mesh.position.set(x, y, z);
      model.add(mesh);

      return mesh;
    };

    // terrain tile;
    // soil base
    // grass top at y=0
    add(new RoundedBoxGeometry(11.1, 0.45, 6.1, 6, 0.3), mat(0x8a6b47), 0, -0.42, 0); 
    add(new RoundedBoxGeometry(10.7, 0.3, 5.7, 6, 0.24), mat(0xbcd88f), 0, -0.14, 0); 

    // field beds (front row), lightly rounded to match
    const beds: [number, number][] = [
      [-3.2, 0xa9d17f],
      [0, 0xcbd98a],
      [3.2, 0xcbd98a],
    ];

    beds.forEach(([x, c]) => add(new RoundedBoxGeometry(2.6, 0.25, 1.7, 4, 0.08), mat(c), x, 0.12, 1.4));

    // drip emitters on the onion bed
    const drip = mat(0x3f6bb0, { metalness: 0.1 });

    for (let i = 0; i < 5; i++) add(new THREE.SphereGeometry(0.07, 8, 8), drip, -4.1 + i * 0.45, 0.28, 1.4);

    // sprinkler risers on wheat and barley
    const metalGrey = mat(0x9aa0a6, { metalness: 0.3 });

    add(new THREE.CylinderGeometry(0.05, 0.05, 0.5, 8), metalGrey, 0, 0.35, 1.4);
    add(new THREE.CylinderGeometry(0.05, 0.05, 0.5, 8), metalGrey, 3.2, 0.35, 1.4);

    // water reserve + pump (left, back row)
    add(new THREE.CylinderGeometry(1, 1, 1.9, 20), mat(0xdfe7ee, { metalness: 0.2, roughness: 0.5 }), -3.4, 0.95, -1.2);
    add(new THREE.CylinderGeometry(0.92, 0.92, 1.35, 20), mat(0x7fb8de, { roughness: 0.35 }), -3.4, 0.7, -1.2);
    add(new THREE.BoxGeometry(0.5, 0.5, 0.5), metalGrey, -2.35, 0.25, -1.2);

    // solar LoRaWAN gateway + ESP32 edge controller + battery (centre)
    add(new THREE.CylinderGeometry(0.07, 0.07, 2.6, 10), metalGrey, 0, 1.3, -1.4);

    // fixed-tilt solar array: an aluminium frame, a glassy panel and a raised PV cell grid, angled up and toward the front like a real roof/ground array.
    const solar = new THREE.Group();
    const frameMat = mat(0xb9c1c9, { metalness: 0.6, roughness: 0.35 });
    const glassMat = mat(0x16233f, { metalness: 0.7, roughness: 0.18 });
    const cellMat = mat(0x30508f, { metalness: 0.5, roughness: 0.3 });
    const W = 2.0;
    const D = 1.25;

    solar.add(new THREE.Mesh(new RoundedBoxGeometry(W, 0.06, D, 3, 0.03), frameMat));

    const glass = new THREE.Mesh(new THREE.BoxGeometry(W - 0.14, 0.04, D - 0.14), glassMat);

    glass.position.y = 0.045;
    solar.add(glass);

    const cols = 6;
    const rows = 3;
    const gap = 0.035;
    const cw = (W - 0.14 - gap * (cols + 1)) / cols;
    const cd = (D - 0.14 - gap * (rows + 1)) / rows;

    for (let i = 0; i < cols; i++) {
      for (let j = 0; j < rows; j++) {
        const cell = new THREE.Mesh(new THREE.BoxGeometry(cw, 0.02, cd), cellMat);

        cell.position.set(
          -(W - 0.14) / 2 + gap + cw / 2 + i * (cw + gap),
          0.075,
          -(D - 0.14) / 2 + gap + cd / 2 + j * (cd + gap),
        );

        solar.add(cell);
      }
    }

    // tilt up and toward the front, squarely aligned
    solar.position.set(0, 2.58, -1.35);
    solar.rotation.set(0.6, 0, 0); 
    model.add(solar);

    // mounting bracket
    add(new THREE.BoxGeometry(0.1, 0.5, 0.1), metalGrey, 0, 2.34, -1.3); 

    // controller cabinet & battery
    add(new THREE.BoxGeometry(0.55, 0.6, 0.36), mat(0xdcdcdc), 0, 1.5, -1.35); 
    add(new THREE.BoxGeometry(0.3, 0.26, 0.22), mat(0xd3d38f), 0, 0.98, -1.15); 

    // per-zone control node (right): stake + sensor + valve + radio
    // - sensor head
    // - solenoid valve
    // - radio node
    add(new THREE.CylinderGeometry(0.05, 0.05, 0.95, 8), metalGrey, 3.4, 0.47, -0.6);
    add(new THREE.BoxGeometry(0.24, 0.2, 0.16), mat(0x3f7bb0), 3.4, 0.98, -0.6); 
    add(new THREE.BoxGeometry(0.34, 0.32, 0.32), mat(0xc0392b), 3.75, 0.22, -0.35); 
    add(new THREE.BoxGeometry(0.3, 0.24, 0.2), mat(0xdcdcdc), 3.05, 0.78, -0.75); 

    // main supply pipe along the ground
    add(new THREE.BoxGeometry(6.6, 0.1, 0.1), mat(0x7c8a97, { metalness: 0.3 }), 0.1, 0.05, -0.4);

    function resize() {
      const w = el.clientWidth || 520;
      const h = el.clientHeight || 330;

      renderer.setSize(w, h, false);

      const asp = w / h;

      cam.left = (-viewSize * asp) / 2;
      cam.right = (viewSize * asp) / 2;
      cam.top = viewSize / 2;
      cam.bottom = -viewSize / 2;
      cam.updateProjectionMatrix();
    }
    
    resize();

    const ro = new ResizeObserver(resize);
    
    ro.observe(el);

    // drag to spin, gentle auto-motion otherwise
    let dragging = false;
    let lastX = 0;
    let userRot = 0;

    const onDown = (e: PointerEvent) => {
      dragging = true;
      lastX = e.clientX;
      el.style.cursor = "grabbing";
    };

    const onMove = (e: PointerEvent) => {
      if (!dragging) return;
      userRot += (e.clientX - lastX) * 0.01;
      lastX = e.clientX;
    };

    const onUp = () => {
      dragging = false;
      el.style.cursor = "grab";
    };

    renderer.domElement.addEventListener("pointerdown", onDown);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);

    const start = performance.now();
    let raf = 0;

    const loop = () => {
      const t = (performance.now() - start) / 1000;
      model.rotation.y = 0.62 + Math.sin(t * 0.5) * 0.16 + userRot;
      renderer.render(scene, cam);
      raf = requestAnimationFrame(loop);
    };

    loop();

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onDown);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      renderer.dispose();

      scene.traverse((o) => {

        if (o instanceof THREE.Mesh) {
          o.geometry.dispose();
          const m = o.material;
          
          if (Array.isArray(m)) m.forEach((mm) => mm.dispose());
          else m.dispose();
        }
      });

      if (renderer.domElement.parentNode === el) el.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={mount} className="hero-3d" aria-label="3D render of the full AquaReserve install" />;
}
