import { motion } from "framer-motion";
import { Music2, Sparkles } from "lucide-react";

function AudioVisualizer() {
  const bars = [
    28, 42, 34, 58, 76, 48, 88, 62, 40, 72,
    94, 54, 68, 82, 46, 64, 36, 78, 52, 30,
    60, 86, 44, 70, 38, 56, 80, 48, 66, 34,
  ];

  return (
    <div className="relative w-full max-w-xl mx-auto">

      {/* Outer Glow */}
      <div className="absolute inset-0 rounded-[2rem] bg-purple-600/10 blur-3xl" />

      {/* Main Visualizer Card */}
      <motion.div
        initial={{ opacity: 0, scale: 0.94, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.25 }}
        className="
          relative
          overflow-hidden
          rounded-[2rem]
          border border-white/10
          bg-white/[0.035]
          backdrop-blur-xl
          p-8
          shadow-2xl
        "
      >

        {/* Top Label */}
        <div className="flex items-center justify-between mb-10">

          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/15 border border-purple-400/20">
              <Music2 className="h-5 w-5 text-purple-400" />
            </div>

            <div>
              <p className="text-sm font-medium text-white">
                Audio Analysis
              </p>
              <p className="text-xs text-gray-500">
                AI transcription engine
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 rounded-full border border-purple-400/20 bg-purple-500/10 px-3 py-1.5">
            <motion.span
              animate={{ opacity: [0.4, 1, 0.4] }}
              transition={{
                duration: 1.8,
                repeat: Infinity,
              }}
              className="h-1.5 w-1.5 rounded-full bg-purple-400"
            />

            <span className="text-xs text-purple-300">
              Processing
            </span>
          </div>

        </div>

        {/* AI Core */}
        <div className="relative flex items-center justify-center py-6">

          {/* Outer rings */}
          <motion.div
            animate={{
              scale: [1, 1.08, 1],
              opacity: [0.25, 0.5, 0.25],
            }}
            transition={{
              duration: 3,
              repeat: Infinity,
              ease: "easeInOut",
            }}
            className="
              absolute
              h-36
              w-36
              rounded-full
              border
              border-purple-400/20
            "
          />

          <motion.div
            animate={{
              scale: [1.05, 1, 1.05],
              opacity: [0.15, 0.35, 0.15],
            }}
            transition={{
              duration: 3,
              repeat: Infinity,
              ease: "easeInOut",
              delay: 0.5,
            }}
            className="
              absolute
              h-48
              w-48
              rounded-full
              border
              border-cyan-400/10
            "
          />

          {/* Core */}
          <motion.div
            animate={{
              boxShadow: [
                "0 0 20px rgba(139,92,246,0.15)",
                "0 0 45px rgba(139,92,246,0.35)",
                "0 0 20px rgba(139,92,246,0.15)",
              ],
            }}
            transition={{
              duration: 2.5,
              repeat: Infinity,
              ease: "easeInOut",
            }}
            className="
              relative
              flex
              h-24
              w-24
              items-center
              justify-center
              rounded-full
              border
              border-purple-400/30
              bg-gradient-to-br
              from-purple-500/20
              to-cyan-400/10
              backdrop-blur-xl
            "
          >
            <Sparkles className="h-8 w-8 text-purple-300" />
          </motion.div>

        </div>

        {/* Waveform */}
        <div className="mt-10 flex h-20 items-center justify-center gap-1.5 overflow-hidden">

          {bars.map((height, index) => (
            <motion.div
              key={index}
              animate={{
                height: [
                  `${Math.max(height * 0.45, 12)}%`,
                  `${height}%`,
                  `${Math.max(height * 0.55, 15)}%`,
                ],
              }}
              transition={{
                duration: 1.6 + (index % 5) * 0.15,
                repeat: Infinity,
                repeatType: "mirror",
                ease: "easeInOut",
                delay: index * 0.04,
              }}
              className="
                w-1.5
                rounded-full
                bg-gradient-to-t
                from-purple-600/30
                via-purple-400/70
                to-cyan-300/80
              "
            />
          ))}

        </div>

        {/* Bottom Flow */}
        <div className="mt-8 grid grid-cols-3 gap-3">

          {["Audio", "AI Analysis", "Notation"].map((item, index) => (
            <div
              key={item}
              className="relative rounded-xl border border-white/5 bg-black/20 px-3 py-3 text-center"
            >
              <p className="text-[11px] text-gray-500">
                {index + 1}
              </p>

              <p className="mt-1 text-xs font-medium text-gray-300">
                {item}
              </p>

              {index < 2 && (
                <span className="absolute -right-2 top-1/2 hidden h-px w-2 bg-purple-400/30 sm:block" />
              )}
            </div>
          ))}

        </div>

      </motion.div>
    </div>
  );
}

export default AudioVisualizer;