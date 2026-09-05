import { motion } from "framer-motion";
import { ArrowRight, Play } from "lucide-react";
import AudioVisualizer from "./AudioVisualizer";

function Hero() {
  return (
    <section
      id="home"
      className="
        relative
        min-h-[calc(100vh-80px)]
        overflow-hidden
        flex
        items-center
        pt-16
        pb-24
      "
    >

      <div className="max-w-7xl mx-auto w-full px-8">

        <div className="grid lg:grid-cols-2 gap-16 lg:gap-20 items-center">

          {/* Left Content */}
          <div className="text-center lg:text-left">

            {/* Badge */}
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="
                inline-flex
                items-center
                gap-2
                rounded-full
                border
                border-purple-400/20
                bg-purple-500/[0.07]
                px-4
                py-2
                text-xs
                font-medium
                tracking-wide
                text-purple-300
              "
            >
              <span className="h-1.5 w-1.5 rounded-full bg-purple-400" />

              AI-POWERED MUSIC TRANSCRIPTION
            </motion.div>

            {/* Heading */}
            <motion.h1
              initial={{ opacity: 0, y: 25 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.1 }}
              className="
                mt-7
                text-5xl
                sm:text-6xl
                lg:text-7xl
                font-bold
                leading-[1.05]
                tracking-tight
                text-white
              "
            >
              Transform Music
              <br />

              <span className="bg-gradient-to-r from-purple-400 via-purple-300 to-cyan-300 bg-clip-text text-transparent">
                Into Notation.
              </span>
            </motion.h1>

            {/* Description */}
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.2 }}
              className="
                mt-7
                max-w-xl
                mx-auto
                lg:mx-0
                text-base
                sm:text-lg
                leading-8
                text-gray-400
              "
            >
              Turn audio recordings into musical notation with
              AI-powered transcription. Detect instruments, extract
              notes, generate MIDI, and create sheet music.
            </motion.p>

            {/* Buttons */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.3 }}
              className="
                mt-9
                flex
                flex-col
                sm:flex-row
                items-center
                justify-center
                lg:justify-start
                gap-4
              "
            >

              {/* Primary CTA */}
              <motion.a
                href="#ai-workspace"
                whileHover={{
                  scale: 1.04,
                  boxShadow: "0 0 30px rgba(139,92,246,0.25)",
                }}
                whileTap={{ scale: 0.97 }}
                className="
                  group
                  flex
                  items-center
                  gap-2
                  rounded-xl
                  bg-purple-600
                  px-6
                  py-3.5
                  font-medium
                  text-white
                  transition-colors
                  hover:bg-purple-500
                "
              >
                Start Transcribing

                <ArrowRight
                  className="
                    h-4
                    w-4
                    transition-transform
                    duration-300
                    group-hover:translate-x-1
                  "
                />
              </motion.a>

              {/* Secondary CTA */}
              <motion.a
                href="#workflow"
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                className="
                  flex
                  items-center
                  gap-2
                  rounded-xl
                  border
                  border-white/10
                  bg-white/[0.03]
                  px-6
                  py-3.5
                  font-medium
                  text-gray-300
                  transition-all
                  duration-300
                  hover:border-purple-400/30
                  hover:bg-white/[0.06]
                  hover:text-white
                "
              >
                <Play className="h-4 w-4 fill-current" />

                See How It Works
              </motion.a>

            </motion.div>

            {/* Supported Instruments */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.8, delay: 0.5 }}
              className="
                mt-10
                flex
                flex-wrap
                items-center
                justify-center
                lg:justify-start
                gap-x-5
                gap-y-2
                text-xs
                text-gray-500
              "
            >
              <span>Supports</span>
              <span className="text-gray-300">Piano</span>
              <span className="text-gray-300">Guitar</span>
              <span className="text-gray-300">Flute</span>
              <span className="text-purple-400">Tabla (Experimental)</span>
            </motion.div>

          </div>

          {/* Right Visual */}
          <motion.div
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.9, delay: 0.25 }}
            className="relative"
          >
            <AudioVisualizer />

            {/* Small floating label */}
            <motion.div
              animate={{
                y: [0, -8, 0],
              }}
              transition={{
                duration: 4,
                repeat: Infinity,
                ease: "easeInOut",
              }}
              className="
                absolute
                -top-5
                -right-2
                sm:right-4
                rounded-xl
                border
                border-white/10
                bg-black/60
                px-4
                py-2.5
                backdrop-blur-xl
                shadow-xl
              "
            >
              <p className="text-[10px] uppercase tracking-wider text-gray-500">
                Output
              </p>

              <p className="mt-0.5 text-xs font-medium text-purple-300">
                Musical Notation
              </p>
            </motion.div>

          </motion.div>

        </div>

      </div>

    </section>
  );
}

export default Hero;
