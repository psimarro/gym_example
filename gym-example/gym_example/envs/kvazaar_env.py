import gym
from gym.utils import seeding
from gym.spaces import Dict, Box, Discrete
import numpy as np
import subprocess
import bisect

class Kvazaar_v0 (gym.Env):
    
    # De momento estas constantes no son muy útiles
    MAX_STEPS = 10
    REWARD_POSITIVE = 1
    REWARD_NEGATIVE = 0

    metadata = {
        "render.modes": ["human"]
    }


    def __init__(self, **kwargs):
        self.kvazaar_path = kwargs.get("kvazaar_path")
        self.vid_path = kwargs.get("vid_path")
        self.nCores = kwargs.get("nCores")
        self.intervalos = kwargs.get("intervalos")
        
        self.action_space = Discrete(self.nCores)
        #El espacio de acciones corresponde a los cores, de 0 a nCores-1
        #el espacio de observaciones es un rango de floats de 0 a 200
        self.observation_space = Box(low=np.array([0]), high=np.array([200]), dtype=np.float32)
        self.goal = 0 #no hay objetivo de momento
        self.kvazaar = None

        self.seed() #generamos semilla de randoms
        # self.reset() #generamos la primera observacion
    
    def reset(self):
        self.reset_kvazaar()
        
        self.count = 0
        # self.state = {"intervalo": 0, "fps" :0} #el estado del entorno en un momento dado es el número de frames devueltos por kvazaar para un bloque 
        self.state = [0]
        self.reward = 0 #la recompensa inicial es 0
        self.done = False
        self.info = {"estado": "inicio"}
        return self.state

    def reset_kvazaar(self):
        comando = [self.kvazaar_path, 
                   "--input", self.vid_path, 
                   "--output", "/dev/null", 
                   "--preset=ultrafast", 
                   "--qp=22", "--owf=0", 
                   "--threads=" + str(self.nCores)]

        # creamos subproceso de kvazaar
        
        if self.kvazaar is None or self.kvazaar.poll() is not None:
            self.kvazaar = subprocess.Popen(comando, 
                                        stdin=subprocess.PIPE, 
                                        stdout=subprocess.PIPE, 
                                        universal_newlines=True, bufsize=1, 
                                        env={'NUM_FRAMES_PER_BATCH': '24'})
    
    def step(self, action):
        
        # if self.done:
        #     #self.reset_kvazaar()
        #     pass
        # else:

        
        assert self.action_space.contains(action)
        action += 1 #ya que el espacio va de 0 a nCores-1
        
        # LLAMADA A KVAZAAR
        s = "nThs:" + str(action)
        self.kvazaar.stdin.write(s + "\n")
        output= self.kvazaar.stdout.readline().strip()
        ########
        
        self.calculate_state(output=output)
    
        self.info["estado"] = output.strip()
        if self.info["estado"] != 'END':
            self.count += 1

        try:
            assert self.observation_space.contains(self.state) #comprabamos que el nuevo estado es válido
        except AssertionError:
            print("INVALID STATE", self.state)

        return [self.state, self.calculate_reward(), self.done, self.info]
    
    def calculate_reward(self):
        if self.info["estado"] == 'END':
            self.reward = self.REWARD_NEGATIVE
        elif self.state[0] < 24:
            self.reward = self.REWARD_NEGATIVE
        else:
            self.reward = self.REWARD_POSITIVE

        return self.reward

    def calculate_state(self, output):
        if(output == "END"):
            self.done = True
            self.info["estado"] = 'END'
        else:
            ## eliminamos la primera parte de la salida ("FPS:") y la guardamos en el nuevo estado
            output_value = np.float32(output[4:])
            self.state = [output_value]
            # self.state["intervalo"] = bisect.bisect_left(self.intervalos, output_value)
            # self.state["fps"] = output_value



    def render(self, mode="human"):
        if self.info["estado"] == 'END':
            print (self.info)
        else:
            print((self.state[0]), self.reward)


    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]
        
    def close(self):
        pass
