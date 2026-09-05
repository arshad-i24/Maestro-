import { motion } from "framer-motion";
import { Code2, Cpu, Database, Zap, Music, Brain } from "lucide-react";


function Technologies() {


  const technologies = [

    {
      icon: Code2,
      name: "Python",
      description:
      "Backend development and AI processing pipeline."
    },


    {
      icon: Zap,
      name: "FastAPI",
      description:
      "High-performance API framework for model integration."
    },


    {
      icon: Brain,
      name: "Spotify Basic Pitch",
      description:
      "Neural network for audio-to-MIDI transcription."
    },


    {
      icon: Music,
      name: "Librosa",
      description:
      "Advanced multi-track music transcription model."
    },


    {
      icon: Database,
      name: "PreetyMIDI",
      description:
      "Music analysis and symbolic notation processing."
    },


    {
      icon: Code2,
      name: "React + Tailwind",
      description:
      "Modern frontend interface and user experience."
    }

  ];



  return (

    <section
      id="technology"
      className="
      py-24
      px-8
      "
    >


      <div className="max-w-7xl mx-auto">


        <div className="text-center mb-16">


          <h2 className="
          text-5xl
          font-bold
          ">

            Technologies Behind Maestro

          </h2>


          <p className="
          text-gray-400
          mt-4
          ">

            Built using modern AI models, audio processing libraries,
            and scalable web technologies.

          </p>


        </div>




        <div className="
        grid
        md:grid-cols-3
        gap-6
        ">


          {technologies.map((tech,index)=>{


            const Icon = tech.icon;


            return (

              <motion.div

                key={index}

                initial={{
                  opacity:0,
                  y:40
                }}

                whileInView={{
                  opacity:1,
                  y:0
                }}

                transition={{
                  duration:0.5,
                  delay:index*0.1
                }}


                whileHover={{
                  y:-8
                }}

                className="
                bg-[#111111]
                border
                border-white/10
                rounded-2xl
                p-8
                hover:border-cyan-400/40
                transition
                "

              >


                <Icon

                  size={45}

                  className="
                  text-cyan-400
                  "
                />



                <h3 className="
                text-2xl
                font-bold
                mt-6
                ">

                  {tech.name}

                </h3>



                <p className="
                text-gray-400
                mt-3
                ">

                  {tech.description}

                </p>


              </motion.div>

            )


          })}



        </div>


      </div>


    </section>

  );

}


export default Technologies;