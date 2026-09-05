import { motion } from "framer-motion";

function Background() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none bg-[#050505]">

      {/* Main Purple Glow */}
      <motion.div
        animate={{
          x: [0, 120, -80, 0],
          y: [0, -80, 60, 0],
          scale: [1, 1.08, 0.95, 1],
        }}
        transition={{
          duration: 22,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="
          absolute
          top-10
          left-10
          w-[500px]
          h-[500px]
          rounded-full
          bg-purple-600/10
          blur-[140px]
        "
      />

      {/* Cyan Glow */}
      <motion.div
        animate={{
          x: [0, -150, 80, 0],
          y: [0, 100, -100, 0],
          scale: [1, 0.92, 1.08, 1],
        }}
        transition={{
          duration: 28,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="
          absolute
          bottom-0
          right-0
          w-[450px]
          h-[450px]
          rounded-full
          bg-cyan-500/10
          blur-[140px]
        "
      />

      {/* Subtle Central Purple Glow */}
      <motion.div
        animate={{
          x: [0, -60, 50, 0],
          y: [0, 50, -40, 0],
          opacity: [0.04, 0.07, 0.04],
        }}
        transition={{
          duration: 30,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className="
          absolute
          top-[35%]
          left-[40%]
          w-[350px]
          h-[350px]
          rounded-full
          bg-purple-500
          blur-[160px]
        "
      />

    </div>
  );
}

export default Background;